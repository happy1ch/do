#!/usr/bin/env python3
"""
Theological Book Pipeline Web Studio (Web GUI)
==============================================
최성광 목사님의 4단계 대용량 전자책(PDF/EPUB) 병렬 추출·검증 웹 스튜디오

- 브라우저에서 드래그 앤 드롭으로 파일 업로드
- 작업 폴더 설정 및 책별 하위 폴더 자동 생성 (output/{책이름}/)
- 실시간 4단계 파이프라인 실행 및 성경 구절 인용 검증
- 원클릭 윈도우 탐색기 폴더 열기 및 통합 마크다운 다운로드

Author: Happy초이 (최성광 목사님의 전속 AI 비서)
"""

import os
import sys
import json
import time
import urllib.parse
import webbrowser
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

# 파이프라인 코어 모듈 임포트
try:
    from book_pipeline import BookSplitter, ConcurrentWorkerEngine, IntegrityVerifier, ResultExporter, get_book_output_dir
except ImportError:
    # 같은 디렉토리에서 임포트
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from book_pipeline import BookSplitter, ConcurrentWorkerEngine, IntegrityVerifier, ResultExporter, get_book_output_dir

HTML_PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>신학 전자책 파이프라인 스튜디오 | 최성광 목사</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Do+Hyeon&family=Noto+Sans+KR:wght@400;500;700&display=swap">
<style>
:root {
  --bg: #0f172a; --surface: #1e293b; --surface-hover: #334155; --border: #334155;
  --text: #f8fafc; --text-dim: #94a3b8; --accent: #38bdf8; --accent-soft: rgba(56, 189, 248, 0.12);
  --success: #10b981; --success-soft: rgba(16, 185, 129, 0.15);
  --warning: #f59e0b; --warning-soft: rgba(245, 158, 11, 0.15);
  --font-display: 'Do Hyeon', sans-serif;
  --font-body: 'Noto Sans KR', system-ui, sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--text); font-family: var(--font-body);
  min-height: 100vh; padding: 40px 20px; line-height: 1.6;
}
.container { max-width: 900px; margin: 0 auto; }

header { text-align: center; margin-bottom: 36px; }
.badge {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700;
  color: var(--accent); background: var(--accent-soft); padding: 5px 14px;
  border-radius: 999px; border: 1px solid var(--accent); margin-bottom: 14px;
}
h1 { font-family: var(--font-display); font-size: clamp(28px, 5vw, 42px); font-weight: 400; margin-bottom: 10px; }
header p { color: var(--text-dim); font-size: 16px; max-width: 580px; margin: 0 auto; }

.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 28px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}
.card-title { font-size: 18px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }

/* Upload Zone */
.dropzone {
  border: 2px dashed #475569; border-radius: 14px; padding: 48px 20px; text-align: center;
  cursor: pointer; transition: all 0.2s ease; background: rgba(15, 23, 42, 0.4);
}
.dropzone:hover, .dropzone.dragover { border-color: var(--accent); background: var(--accent-soft); }
.dropzone-icon { font-size: 48px; margin-bottom: 12px; }
.dropzone-text { font-size: 17px; font-weight: 700; margin-bottom: 6px; }
.dropzone-sub { font-size: 13.5px; color: var(--text-dim); }
#fileInput { display: none; }

.file-selected {
  margin-top: 16px; padding: 12px 18px; border-radius: 10px; background: rgba(56, 189, 248, 0.08);
  border: 1px solid var(--accent); display: none; align-items: center; justify-content: space-between;
}
.file-info { font-weight: 700; font-size: 15px; color: var(--accent); display: flex; align-items: center; gap: 8px; }
.file-size { font-size: 13px; color: var(--text-dim); font-weight: 400; }

/* Settings */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 640px) { .grid-2 { grid-template-columns: 1fr; } }
.form-group { margin-bottom: 16px; }
label { display: block; font-size: 13.5px; font-weight: 700; margin-bottom: 6px; color: var(--text-dim); }
input[type="text"], input[type="number"] {
  width: 100%; padding: 11px 14px; border-radius: 8px; border: 1px solid var(--border);
  background: #0f172a; color: #fff; font-size: 15px; font-family: inherit;
}
input[type="text"]:focus, input[type="number"]:focus { outline: none; border-color: var(--accent); }
.checkbox-label {
  display: flex; align-items: center; gap: 10px; font-size: 14.5px; font-weight: 500; cursor: pointer;
  color: var(--text); user-select: none; margin-top: 8px;
}
.checkbox-label input { width: 18px; height: 18px; cursor: pointer; accent-color: var(--accent); }

/* Run Button */
.btn-run {
  width: 100%; padding: 16px; border-radius: 12px; border: none; cursor: pointer;
  background: linear-gradient(135deg, #0284c7, #2563eb); color: #fff;
  font-family: var(--font-display); font-size: 20px; letter-spacing: 0.5px;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35); transition: all 0.2s ease;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.btn-run:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(37, 99, 235, 0.45); }
.btn-run:disabled { opacity: 0.5; cursor: not-allowed; }

/* Progress */
.progress-card { display: none; }
.progress-bar-bg { width: 100%; height: 10px; background: #0f172a; border-radius: 99px; overflow: hidden; margin: 16px 0; }
.progress-bar-fill { height: 100%; width: 0%; background: var(--accent); transition: width 0.3s ease; }
.status-log {
  background: #090d16; border: 1px solid var(--border); border-radius: 10px;
  padding: 16px; font-family: 'Consolas', monospace; font-size: 13.5px;
  color: #a5f3fc; max-height: 220px; overflow-y: auto; line-height: 1.6;
}

/* Results */
.result-card { display: none; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }
.stat-box {
  background: #0f172a; border: 1px solid var(--border); border-radius: 12px; padding: 18px; text-align: center;
}
.stat-val { font-family: var(--font-display); font-size: 30px; color: var(--accent); margin-bottom: 4px; }
.stat-label { font-size: 13px; color: var(--text-dim); }

.action-btns { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px; }
.btn-action {
  padding: 12px 20px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface-hover); color: #fff; font-size: 14.5px; font-weight: 700;
  text-decoration: none; cursor: pointer; display: inline-flex; align-items: center; gap: 8px;
  transition: all 0.15s ease;
}
.btn-action:hover { background: var(--accent); color: #0f172a; border-color: var(--accent); }
.btn-primary-action {
  background: var(--accent); color: #0f172a; border-color: var(--accent);
}
.btn-primary-action:hover { opacity: 0.9; }

/* Chapter List */
.chapter-accordion { margin-top: 24px; }
.ch-item {
  border-bottom: 1px solid var(--border); padding: 12px 0; display: flex; justify-content: space-between;
  font-size: 14px;
}
.ch-item:last-child { border-bottom: none; }
.ch-title { font-weight: 600; color: #f1f5f9; }
.ch-meta { color: var(--text-dim); font-size: 12.5px; }
</style>
</head>
<body>
<div class="container">

  <header>
    <div class="badge">✦ THEOLOGICAL BOOK PIPELINE STUDIO ✦</div>
    <h1>신학 도서 자동 추출 & 검증 스튜디오</h1>
    <p>최성광 목사님의 4단계 아키텍처 기반: PDF나 EPUB 전자책을 올리시면 챕터 분할·병렬 정제·성경 구절 검증까지 책별 전용 폴더로 자동 완성됩니다.</p>
  </header>

  <!-- 1. 파일 업로드 -->
  <div class="card">
    <div class="card-title"><span>📂</span> 1. 책 파일 불러오기 (.pdf, .epub)</div>
    <div class="dropzone" id="dropzone">
      <div class="dropzone-icon">📖</div>
      <div class="dropzone-text">마우스로 PDF나 EPUB 파일을 여기에 끌어다 놓으세요</div>
      <div class="dropzone-sub">또는 클릭하여 내 컴퓨터에서 파일 선택</div>
      <input type="file" id="fileInput" accept=".pdf,.epub">
    </div>
    <div class="file-selected" id="fileSelected">
      <div class="file-info">
        <span>📄</span>
        <span id="selectedFileName">파일명</span>
        <span class="file-size" id="selectedFileSize">(0 MB)</span>
      </div>
      <button type="button" id="btnRemoveFile" style="background:none;border:none;color:#ef4444;font-size:18px;cursor:pointer;">✕</button>
    </div>
  </div>

  <!-- 2. 작업 설정 -->
  <div class="card">
    <div class="card-title"><span>⚙️</span> 2. 작업 및 저장 폴더 설정</div>
    <div class="grid-2">
      <div class="form-group">
        <label for="outputDir">출력 상위 폴더 경로</label>
        <input type="text" id="outputDir" value="output" placeholder="예: output 또는 C:/MyBooks">
      </div>
      <div class="form-group">
        <label for="workerCount">동시 병렬 처리 스레드 (CPU 워커)</label>
        <input type="number" id="workerCount" value="6" min="1" max="16">
      </div>
    </div>
    <label class="checkbox-label">
      <input type="checkbox" id="createSubfolder" checked>
      <span><strong>책별 전용 폴더 자동 생성</strong> (예: <code>output/Reformed Dogmatics v1.2/</code> 로 분리 보존)</span>
    </label>
  </div>

  <!-- 3. 실행 버튼 -->
  <button type="button" class="btn-run" id="btnRun" disabled>
    <span>🚀</span> 4단계 파이프라인 가동하기
  </button>

  <!-- 4. 실시간 진행 상태 -->
  <div class="card progress-card" id="progressCard" style="margin-top:24px;">
    <div class="card-title"><span>⏳</span> 파이프라인 처리 중...</div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" id="progressBar"></div>
    </div>
    <div class="status-log" id="statusLog">파이프라인 준비 중...\n</div>
  </div>

  <!-- 5. 결과 대시보드 -->
  <div class="card result-card" id="resultCard" style="margin-top:24px;">
    <div class="card-title"><span>🎉</span> 파이프라인 완료! (결과 대시보드)</div>
    
    <div class="stat-grid">
      <div class="stat-box">
        <div class="stat-val" id="resChapters">0개</div>
        <div class="stat-label">추출된 챕터 수</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="resWords">0자</div>
        <div class="stat-label">전체 텍스트 글자 수</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="resRefs" style="color:#10b981;">0개</div>
        <div class="stat-label">감지된 성경 인용 구절</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="resStatus" style="font-size:22px;padding-top:6px;">통과 (정상)</div>
        <div class="stat-label">2중 무결성 검증 결과</div>
      </div>
    </div>

    <div style="background:#090d16;padding:14px 18px;border-radius:10px;border:1px solid var(--border);margin-bottom:16px;">
      <div style="font-size:12.5px;color:var(--text-dim);margin-bottom:4px;">저장된 책별 전용 폴더 경로:</div>
      <code id="resFolderPath" style="color:var(--accent);font-size:14px;word-break:break-all;"></code>
    </div>

    <div class="action-btns">
      <button type="button" class="btn-action btn-primary-action" id="btnOpenExplorer">
        📁 내 컴퓨터에서 결과 폴더 열기 (Explorer)
      </button>
      <a class="btn-action" id="btnDownloadMd" href="#" download>
        📄 통합 마크다운(.md) 다운로드
      </a>
      <a class="btn-action" id="btnDownloadJson" href="#" download>
        📊 검증 보고서(.json) 다운로드
      </a>
    </div>

    <div class="chapter-accordion">
      <h3 style="font-size:16px;margin-bottom:12px;color:var(--text-dim);">📑 챕터별 세부 내역</h3>
      <div id="chapterList" style="max-height:300px;overflow-y:auto;background:#090d16;padding:12px 18px;border-radius:10px;border:1px solid var(--border);"></div>
    </div>
  </div>

</div>

<script>
let currentFile = null;
let currentResult = null;

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const fileSelected = document.getElementById('fileSelected');
const selectedFileName = document.getElementById('selectedFileName');
const selectedFileSize = document.getElementById('selectedFileSize');
const btnRemoveFile = document.getElementById('btnRemoveFile');
const btnRun = document.getElementById('btnRun');
const progressCard = document.getElementById('progressCard');
const progressBar = document.getElementById('progressBar');
const statusLog = document.getElementById('statusLog');
const resultCard = document.getElementById('resultCard');

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
  e.preventDefault(); dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length) handleFile(e.target.files[0]);
});

function handleFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'pdf' && ext !== 'epub') {
    alert('PDF 또는 EPUB 파일만 지원합니다.');
    return;
  }
  currentFile = file;
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = `(${(file.size / (1024*1024)).toFixed(2)} MB)`;
  dropzone.style.display = 'none';
  fileSelected.style.display = 'flex';
  btnRun.disabled = false;
}

btnRemoveFile.addEventListener('click', () => {
  currentFile = null;
  fileInput.value = '';
  dropzone.style.display = 'block';
  fileSelected.style.display = 'none';
  btnRun.disabled = true;
});

function appendLog(msg) {
  statusLog.textContent += msg + '\n';
  statusLog.scrollTop = statusLog.scrollHeight;
}

btnRun.addEventListener('click', async () => {
  if (!currentFile) return;

  btnRun.disabled = true;
  progressCard.style.display = 'block';
  resultCard.style.display = 'none';
  progressBar.style.width = '20%';
  statusLog.textContent = '';
  appendLog(`🚀 [시작] 파일 전송 및 분석 준비: ${currentFile.name}`);

  const outputDir = document.getElementById('outputDir').value.trim() || 'output';
  const workerCount = document.getElementById('workerCount').value || 6;
  const createSubfolder = document.getElementById('createSubfolder').checked ? '1' : '0';

  appendLog(`📁 설정 확인: 출력 경로 = ${outputDir}, 워커 = ${workerCount}개, 책별 폴더 = ${createSubfolder === '1' ? '예' : '아니오'}`);
  progressBar.style.width = '40%';
  appendLog(`⏳ [1단계 & 2단계] 챕터 분할 및 동시 병렬 처리 가동 중...`);

  try {
    const url = `/api/process?filename=${encodeURIComponent(currentFile.name)}&output_dir=${encodeURIComponent(outputDir)}&workers=${workerCount}&subfolder=${createSubfolder}`;
    const resp = await fetch(url, {
      method: 'POST',
      body: currentFile
    });

    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(err || '서버 처리 오류');
    }

    progressBar.style.width = '80%';
    appendLog(`👉 [3단계 & 4단계] 2중 무결성 검증 및 다중 포맷 빌드 완료!`);
    
    const data = await resp.json();
    currentResult = data;
    progressBar.style.width = '100%';
    appendLog(`🎉 [완료] 소요 시간: ${data.elapsed_seconds}초! 결과물이 생성되었습니다.`);

    renderResult(data);
  } catch (err) {
    appendLog(`❌ [오류 발생]: ${err.message}`);
    alert('처리 중 오류가 발생했습니다: ' + err.message);
  } finally {
    btnRun.disabled = false;
  }
});

function renderResult(data) {
  resultCard.style.display = 'block';
  document.getElementById('resChapters').textContent = `${data.total_chapters}개`;
  document.getElementById('resWords').textContent = `${data.total_chars.toLocaleString()}자`;
  document.getElementById('resRefs').textContent = `${data.total_bible_refs.toLocaleString()}개`;
  document.getElementById('resStatus').textContent = data.qa_report.all_passed ? '✅ 통과 (정상)' : '⚠️ 주의 필요';
  document.getElementById('resStatus').style.color = data.qa_report.all_passed ? '#10b981' : '#f59e0b';
  document.getElementById('resFolderPath').textContent = data.output_folder;

  // 다운로드 링크 설정
  document.getElementById('btnDownloadMd').href = `/api/download?path=${encodeURIComponent(data.paths.markdown)}`;
  document.getElementById('btnDownloadJson').href = `/api/download?path=${encodeURIComponent(data.paths.qa_report)}`;

  // 챕터 목록
  const listEl = document.getElementById('chapterList');
  listEl.innerHTML = '';
  data.chapters.forEach((ch, idx) => {
    const item = document.createElement('div');
    item.className = 'ch-item';
    item.innerHTML = `
      <div class="ch-title">${idx + 1}. ${ch.title}</div>
      <div class="ch-meta">${ch.char_count.toLocaleString()}자 | 성경 인용 ${ch.bible_refs || 0}개</div>
    `;
    listEl.appendChild(item);
  });
}

document.getElementById('btnOpenExplorer').addEventListener('click', async () => {
  if (!currentResult || !currentResult.output_folder) return;
  try {
    const resp = await fetch(`/api/open_folder?path=${encodeURIComponent(currentResult.output_folder)}`, { method: 'POST' });
    const res = await resp.json();
    if (!res.ok) alert('폴더 열기 실패: ' + res.error);
  } catch (e) {
    alert('요청 실패: ' + e.message);
  }
});
</script>
</body>
</html>
"""


class PipelineServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif parsed.path == '/api/download':
            qs = urllib.parse.parse_qs(parsed.query)
            target_path = qs.get('path', [''])[0]
            if os.path.exists(target_path):
                self.send_response(200)
                filename = os.path.basename(target_path)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{urllib.parse.quote(filename)}"')
                self.end_headers()
                with open(target_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/process':
            self.handle_process(parsed)
        elif parsed.path == '/api/open_folder':
            self.handle_open_folder(parsed)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_open_folder(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        target_path = qs.get('path', [''])[0]
        abs_path = os.path.abspath(target_path)
        
        try:
            if sys.platform == 'win32':
                os.startfile(abs_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', abs_path])
            else:
                subprocess.Popen(['xdg-open', abs_path])
            res = {"ok": True}
        except Exception as e:
            res = {"ok": False, "error": str(e)}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(res).encode('utf-8'))

    def handle_process(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        filename = qs.get('filename', ['uploaded_book.bin'])[0]
        base_output_dir = qs.get('output_dir', ['output'])[0]
        workers = int(qs.get('workers', [6])[0])
        create_subfolder = qs.get('subfolder', ['1'])[0] == '1'

        content_length = int(self.headers.get('Content-Length', 0))
        file_bytes = self.rfile.read(content_length)

        # 1. 임시 업로드 폴더에 저장
        temp_dir = os.path.join(base_output_dir, "_temp_uploads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, filename)
        with open(temp_file_path, 'wb') as f:
            f.write(file_bytes)

        t_start = time.time()

        # 2. 책별 폴더 결정
        target_output_dir = get_book_output_dir(base_output_dir, filename) if create_subfolder else base_output_dir
        os.makedirs(target_output_dir, exist_ok=True)

        # 3. 1단계: 분할
        if filename.lower().endswith(".pdf"):
            pages = BookSplitter.extract_pdf_pages(temp_file_path)
            chapters = BookSplitter.detect_pdf_chapters(pages)
        elif filename.lower().endswith(".epub"):
            chapters = BookSplitter.extract_epub_chapters(temp_file_path)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Unsupported file type")
            return

        # 4. 2단계: 동시 병렬 처리
        engine = ConcurrentWorkerEngine(max_workers=workers)
        processed = engine.process_all_parallel(chapters)

        # 5. 3단계: 무결성 검증
        qa_report = IntegrityVerifier.run_full_verification(processed)

        # 6. 4단계: 결과물 빌드
        paths = ResultExporter.export(target_output_dir, processed, qa_report)
        elapsed = round(time.time() - t_start, 2)

        # 챕터별 성구 개수 집계 매핑
        qa_details = {d["chapter_id"]: d.get("bible_reference_count", 0) for d in qa_report.get("chapter_details", [])}
        for c in processed:
            c["bible_refs"] = qa_details.get(c["id"], 0)

        total_chars = sum(c["char_count"] for c in processed)

        resp_data = {
            "ok": True,
            "filename": filename,
            "output_folder": os.path.abspath(target_output_dir),
            "total_chapters": len(processed),
            "total_chars": total_chars,
            "total_bible_refs": qa_report.get("total_bible_references_detected", 0),
            "elapsed_seconds": elapsed,
            "qa_report": qa_report,
            "paths": paths,
            "chapters": [{
                "id": c["id"],
                "title": c["title"],
                "char_count": c["char_count"],
                "bible_refs": c.get("bible_refs", 0)
            } for c in processed]
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(resp_data, ensure_ascii=False).encode('utf-8'))


def run_web_studio(port: int = 8500):
    server = HTTPServer(('127.0.0.1', port), PipelineServerHandler)
    url = f"http://localhost:{port}"
    print(f"===========================================================")
    print(f"🚀 최성광 목사님의 신학 도서 파이프라인 웹 스튜디오 시작!")
    print(f"👉 브라우저 접속 주소: {url}")
    print(f"   (브라우저가 자동으로 열립니다. 종료하려면 Ctrl+C)")
    print(f"===========================================================")
    
    # 브라우저 자동 오픈
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버가 종료되었습니다.")
        server.server_close()


if __name__ == '__main__':
    port = 8500
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_web_studio(port)
