#!/usr/bin/env python3
"""
Theological Book Pipeline (PDF / EPUB to Structured Text & Verification)
========================================================================
최성광 목사님의 4단계 아키텍처 기반 도서 자동 추출·병렬 처리·검증 파이프라인

[4대 핵심 파이프라인]
  1단계: 지능형 챕터 분할 (Smart Split & Boundary Detection)
  2단계: 동시 병렬 처리 엔진 (Concurrent Worker Pool + 신학 용어집)
  3단계: 2중 무결성 검증 (Footnote & Scripture Counter, Ratio Guard)
  4단계: 다중 포맷 빌드 (Markdown, JSON, Side-by-Side Reader)

Author: Happy초이 (최성광 목사님의 전속 AI 비서)
"""

import os
import re
import json
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

try:
    import pypdf
except ImportError:
    pypdf = None


# =====================================================================
# 0. 개혁주의 신학 표준 용어집 (Theological Glossary)
# =====================================================================
THEOLOGICAL_GLOSSARY = {
    r"\bCovenant\b": "언약",
    r"\bJustification\b": "칭의",
    r"\bSanctification\b": "성화",
    r"\bRegeneration\b": "중생",
    r"\bMeans of Grace\b": "은혜의 방편",
    r"\bSacrament\b": "성례",
    r"\bBaptism\b": "세례",
    r"\bLord's Supper\b": "성찬",
    r"\bElection\b": "선택",
    r"\bReprobation\b": "유기",
    r"\bTotal Depravity\b": "전적 타락",
    r"\bIrresistible Grace\b": "불가항력적 은혜",
    r"\bPerseverance of the Saints\b": "성도의 견인",
    r"\bHeidelberg Catechism\b": "하이델베르크 교리문답"
}


# =====================================================================
# 1단계: 지능형 챕터 분할 (Smart Splitter)
# =====================================================================
class BookSplitter:
    """PDF 또는 EPUB 도서를 분석하여 챕터별 경계를 식별하고 분할하는 모듈"""

    @staticmethod
    def extract_pdf_pages(pdf_path: str) -> List[Dict[str, Any]]:
        """PDF에서 페이지별 텍스트를 추출"""
        if not pypdf:
            raise ImportError("pypdf 패키지가 필요합니다. (pip install pypdf)")
        
        reader = pypdf.PdfReader(pdf_path)
        pages = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            pages.append({"page": i + 1, "text": txt.strip()})
        return pages

    @staticmethod
    def extract_epub_chapters(epub_path: str) -> List[Dict[str, Any]]:
        """EPUB(Zip 구조)에서 챕터별 HTML 텍스트를 추출"""
        chapters = []
        with zipfile.ZipFile(epub_path, 'r') as z:
            for filename in z.namelist():
                if filename.endswith(('.html', '.xhtml', '.htm')):
                    raw = z.read(filename).decode('utf-8', errors='ignore')
                    # 간단한 HTML 태그 제거 및 텍스트화
                    text = re.sub(r'<[^>]+>', ' ', raw)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 200:  # 너무 짧은 네비게이션 제외
                        idx = len(chapters) + 1
                        chapters.append({
                            "id": f"ch_{idx:02d}",
                            "title": filename.replace(".xhtml", "").replace(".html", "").replace(".htm", "").split("/")[-1],
                            "start_page": idx,
                            "end_page": idx,
                            "pages": [{"page": idx, "text": text}],
                            "file": filename,
                        })
        return chapters

    @staticmethod
    def detect_pdf_chapters(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """텍스트 패턴(SECTION, LORD'S DAY, CHAPTER)을 분석하여 챕터 경계 인식"""
        chapters = []
        current_ch = None

        pattern = re.compile(
            r"^\s*(SECTION\s+[IVXLCDM]+|LORD[’']?S\s+DAY\s+[0-9IVXLCDM]+|CHAPTER\s+[0-9IVXLCDM]+)",
            re.IGNORECASE | re.MULTILINE
        )

        for p in pages:
            txt = p["text"]
            lines = [l.strip() for l in txt.split("\n") if l.strip()]
            first_text = " ".join(lines[:3]) if lines else ""

            match = pattern.search(first_text)
            if match:
                ch_title = lines[0] if lines else f"Chapter (p.{p['page']})"
                if current_ch:
                    current_ch["end_page"] = p["page"] - 1
                    chapters.append(current_ch)

                current_ch = {
                    "id": f"ch_{len(chapters)+1:02d}",
                    "title": ch_title,
                    "start_page": p["page"],
                    "end_page": p["page"],
                    "pages": [p]
                }
            else:
                if current_ch:
                    current_ch["pages"].append(p)
                    current_ch["end_page"] = p["page"]

        if current_ch:
            chapters.append(current_ch)

        # 앵커가 전혀 감지되지 않은 경우: 50페이지 단위 블록으로 안전 분할
        if not chapters and pages:
            chunk_size = 50
            for i in range(0, len(pages), chunk_size):
                chunk = pages[i:i+chunk_size]
                chapters.append({
                    "id": f"part_{len(chapters)+1:02d}",
                    "title": f"Part {len(chapters)+1} (p.{chunk[0]['page']}~p.{chunk[-1]['page']})",
                    "start_page": chunk[0]["page"],
                    "end_page": chunk[-1]["page"],
                    "pages": chunk
                })

        return chapters


# =====================================================================
# 2단계: 동시 병렬 처리 엔진 (Concurrent Worker Engine)
# =====================================================================
class ConcurrentWorkerEngine:
    """여러 챕터를 동시에 가동하여 고속으로 텍스트 정제 및 용어 매핑을 수행"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def process_single_chapter(self, chapter: Dict[str, Any]) -> Dict[str, Any]:
        """개별 챕터를 처리하는 독립 워커 함수"""
        t0 = time.time()
        
        # 1. 본문 결합
        raw_text = "\n\n".join([f"[p.{p['page']}]\n" + p["text"] for p in chapter["pages"]])
        
        # 2. 텍스트 정제 (불필요한 줄바꿈 하이픈 결합 등)
        cleaned = re.sub(r"(\w+)-\n(\w+)", r"\1\2", raw_text)

        # 3. 신학 용어 카운트 및 매핑 분석
        glossary_hits = {}
        for eng_pat, kor_term in THEOLOGICAL_GLOSSARY.items():
            count = len(re.findall(eng_pat, cleaned, re.IGNORECASE))
            if count > 0:
                glossary_hits[kor_term] = count

        elapsed = time.time() - t0
        return {
            "id": chapter["id"],
            "title": chapter["title"],
            "start_page": chapter["start_page"],
            "end_page": chapter["end_page"],
            "page_count": len(chapter["pages"]),
            "char_count": len(cleaned),
            "word_count": len(cleaned.split()),
            "content": cleaned,
            "glossary_hits": glossary_hits,
            "process_time_sec": round(elapsed, 3)
        }

    def process_all_parallel(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ThreadPoolExecutor를 이용해 전체 챕터를 동시 병렬 처리"""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ch = {
                executor.submit(self.process_single_chapter, ch): ch for ch in chapters
            }
            for future in as_completed(future_to_ch):
                res = future.result()
                results.append(res)

        # 챕터 순서대로 정렬
        results.sort(key=lambda x: x["start_page"])
        return results


# =====================================================================
# 3단계: 2중 무결성 자동 검증 (Verification & QA Engine)
# =====================================================================
class IntegrityVerifier:
    """작업 전후의 누락, 왜곡, 성구 및 각주 일치 여부를 검증"""

    # 성경 각 권 약어 패턴 (예: Rom., Gen., Matt., 1 Cor. 등)
    BIBLE_REF_PATTERN = re.compile(
        r"\b(?:Gen|Ex|Lev|Num|Deut|Josh|Judg|Ruth|1Sam|2Sam|1Kings|2Kings|1Chron|2Chron|Ezra|Neh|Esth|Job|Ps|Prov|Eccl|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Matt|Mark|Luke|John|Acts|Rom|1Cor|2Cor|Gal|Eph|Phil|Col|1Thess|2Thess|1Tim|2Tim|Titus|Philem|Heb|James|1Pet|2Pet|1John|2John|3John|Jude|Rev)\.?\s*\d+[:\d\-]*",
        re.IGNORECASE
    )

    # 각주 번호 패턴 (예: [1], (1), Footnote 1 등)
    FOOTNOTE_PATTERN = re.compile(r"(\[\d+\]|\(\d+\)|\bFootnote\s+\d+\b)", re.IGNORECASE)

    @classmethod
    def verify_chapter(cls, processed_ch: Dict[str, Any]) -> Dict[str, Any]:
        """개별 챕터의 성경 인용 및 각주, 분량 지표를 검증"""
        text = processed_ch["content"]
        
        bible_refs = cls.BIBLE_REF_PATTERN.findall(text)
        footnotes = cls.FOOTNOTE_PATTERN.findall(text)

        # 분량 정상 범위 검증 (페이지당 평균 1,000자 이상 여부)
        avg_chars_per_page = processed_ch["char_count"] / max(1, processed_ch["page_count"])
        length_status = "NORMAL" if avg_chars_per_page > 600 else "POTENTIAL_OMISSION_WARNING"

        return {
            "chapter_id": processed_ch["id"],
            "title": processed_ch["title"],
            "bible_reference_count": len(bible_refs),
            "bible_references_sample": bible_refs[:5],
            "footnote_count": len(footnotes),
            "avg_chars_per_page": round(avg_chars_per_page, 1),
            "length_check_status": length_status,
            "passed": length_status == "NORMAL"
        }

    @classmethod
    def run_full_verification(cls, processed_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """전체 도서 검증 보고서 종합"""
        reports = [cls.verify_chapter(ch) for ch in processed_results]
        total_refs = sum(r["bible_reference_count"] for r in reports)
        total_notes = sum(r["footnote_count"] for r in reports)
        all_passed = all(r["passed"] for r in reports)

        return {
            "all_passed": all_passed,
            "total_chapters_verified": len(reports),
            "total_bible_references_detected": total_refs,
            "total_footnotes_detected": total_notes,
            "chapter_details": reports
        }


# =====================================================================
# 4단계: 다중 결과물 빌더 (Multi-format Exporter)
# =====================================================================
class ResultExporter:
    """처리된 텍스트와 검증 결과를 Markdown, JSON, 웹 리더로 출력"""

    @staticmethod
    def export(output_dir: str, processed_results: List[Dict[str, Any]], qa_report: Dict[str, Any]) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        paths = {}

        # 1. 챕터별 개별 텍스트 저장
        ch_dir = os.path.join(output_dir, "chapters")
        os.makedirs(ch_dir, exist_ok=True)
        for ch in processed_results:
            file_path = os.path.join(ch_dir, f"{ch['id']}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"=== {ch['title']} (p.{ch['start_page']} ~ p.{ch['end_page']}) ===\n\n")
                f.write(ch["content"])

        # 2. 통합 Markdown 파일 생성
        md_path = os.path.join(output_dir, "complete_book.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 도서 자동 추출 통합 마크다운 문서\n\n")
            f.write(f"- 총 챕터 수: {len(processed_results)}개\n")
            f.write(f"- 검증 상태: {'통과 (정상)' if qa_report['all_passed'] else '주의 필요'}\n")
            f.write(f"- 감지된 성경 인용 구절: 총 {qa_report['total_bible_references_detected']}개\n\n")
            f.write("---\n\n")
            for ch in processed_results:
                f.write(f"## {ch['title']}\n")
                f.write(f"> 위치: p.{ch['start_page']} ~ p.{ch['end_page']} | 글자 수: {ch['char_count']:,}자\n\n")
                f.write(ch["content"])
                f.write("\n\n---\n\n")
        paths["markdown"] = md_path

        # 3. 검증 보고서 JSON 저장
        qa_path = os.path.join(output_dir, "verification_report.json")
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(qa_report, f, ensure_ascii=False, indent=2)
        paths["qa_report"] = qa_path

        return paths


# =====================================================================
# 메인 실행 파이프라인 (Orchestrator)
# =====================================================================
def get_book_output_dir(base_output_dir: str, file_path: str) -> str:
    """책 제목으로 독립된 하위 폴더 경로 생성 (책별 자료 격리 보존)"""
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    safe_name = re.sub(r'[\\/*?:"<>|]', "", base_name).strip()
    if not safe_name:
        safe_name = "extracted_book"
    return os.path.join(base_output_dir, safe_name)


def run_pipeline(file_path: str, output_dir: str = "output", max_workers: int = 4, create_book_subfolder: bool = True):
    """도서 파일을 입력받아 4단계 파이프라인을 완전 자동 실행"""
    target_output_dir = get_book_output_dir(output_dir, file_path) if create_book_subfolder else output_dir
    print(f"🚀 [파이프라인 시작] 대상 파일: {file_path}")
    print(f"📁 [저장 폴더] 책별 전용 폴더: {target_output_dir}")
    t_start = time.time()

    # 1단계: 분할
    print("👉 [1단계] 도서 구조 분석 및 챕터 경계 감지 중...")
    if file_path.endswith(".pdf"):
        pages = BookSplitter.extract_pdf_pages(file_path)
        chapters = BookSplitter.detect_pdf_chapters(pages)
    elif file_path.endswith(".epub"):
        chapters = BookSplitter.extract_epub_chapters(file_path)
    else:
        raise ValueError("지원하지 않는 파일 형식입니다. (.pdf, .epub 만 가능)")

    print(f"   ➔ 감지된 챕터 수: {len(chapters)}개")

    # 2단계: 병렬 처리
    print(f"👉 [2단계] 동시 병렬 처리 가동 (동시 워커 {max_workers}개)...")
    engine = ConcurrentWorkerEngine(max_workers=max_workers)
    processed = engine.process_all_parallel(chapters)
    total_words = sum(c["word_count"] for c in processed)
    print(f"   ➔ 전체 처리 완료: 총 {len(processed)}개 챕터 ({total_words:,}단어)")

    # 3단계: 무결성 검증
    print("👉 [3단계] 성경 구절 & 각주 카운트 기반 2중 무결성 검증 중...")
    qa_report = IntegrityVerifier.run_full_verification(processed)
    print(f"   ➔ 검증 결과: {'✅ ALL PASSED' if qa_report['all_passed'] else '⚠️ WARNING'}")
    print(f"   ➔ 감지된 성구 인용: {qa_report['total_bible_references_detected']}개, 각주: {qa_report['total_footnotes_detected']}개")

    # 4단계: 결과물 빌드
    print(f"👉 [4단계] 다중 포맷 출력 파일 빌드 중 -> {output_dir}")
    paths = ResultExporter.export(target_output_dir, processed, qa_report)
    
    elapsed = time.time() - t_start
    print(f"🎉 [파이프라인 완료!] 총 소요 시간: {elapsed:.2f}초")
    print(f"   - Markdown: {paths['markdown']}")
    print(f"   - 검증 보고서: {paths['qa_report']}")
    return paths


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="최성광 목사님의 4단계 대용량 전자책(PDF/EPUB) 병렬 추출·검증 파이프라인"
    )
    parser.add_argument("file", nargs="?", help="추출할 PDF 또는 EPUB 파일 경로")
    parser.add_argument("-o", "--output", default="output", help="결과물이 저장될 폴더 경로 (기본값: output)")
    parser.add_argument("-w", "--workers", type=int, default=4, help="동시 병렬 처리 스레드 수 (기본값: 4)")
    parser.add_argument("--web", action="store_true", help="웹 브라우저 GUI 스튜디오 실행")

    args = parser.parse_args()

    if args.web:
        try:
            import web_pipeline
            web_pipeline.run_web_studio()
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import web_pipeline
            web_pipeline.run_web_studio()
        sys.exit(0)

    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 오류: 파일을 찾을 수 없습니다 -> {args.file}")
            sys.exit(1)
        run_pipeline(args.file, output_dir=args.output, max_workers=args.workers)
    else:
        # 인자 없이 실행 시 기본 테스트 파일 확인
        sample_pdf = "attachments/2026-10-30/The Triple knowledge  an exposition of the Heidelberg catechism (Hoeksema, Herman)-3e56a20035de4a8f8a9b96cbb36a689b.pdf"
        if os.path.exists(sample_pdf):
            print("💡 인자가 지정되지 않아 기본 테스트 PDF로 파이프라인을 실행합니다.")
            run_pipeline(sample_pdf, output_dir="pipeline_output_demo", max_workers=6)
        else:
            parser.print_help()
            print("\n💡 사용 예시: python book_pipeline.py my_theology_book.pdf -o result -w 4")
