# 동물·음식 영상 수집 (워터마크 없는 원본) — 메인 작업

> 2026-11-24부터 이 작업이 메인. 연예·꿀팁·아이돌 자동 실행은 일시정지(삭제 아님).

## 목표
X·쇼츠에 바로 올릴 수 있는 **해외 실사 동물 영상 + 음식 영상**을 워터마크 없는 mp4로 확보. 가끔 동물 짤(이미지)도.

## 선별 기준
- 실사만 (AI 생성·애니메이션 제외. 캡션에 #ai #sora 등 있으면 제외)
- **동물: 1~29초**, 귀엽거나 웃긴 행동·리액션 (사람 얼굴이 주인공인 영상은 피함)
- **음식: 15~55초**, 비주얼 기깔나는 것 (길거리 음식, 초대형 고기·바비큐, 치즈풀, 신기한 조리 과정)
- 조회수 높은 순 우선. 최근 영상이면 가산점
- 제외: 남의 영상 짜깁기 계정(채널 로고가 영상에 박혀 있는 것), 워터마크 없는 원본 스트림이 없는 영상, 이미 받은 영상

## 실행 순서
1. 웹 검색(allowed_domains: tiktok.com)으로 키워드별 영상 URL 후보 수집
   - 동물: funny cat, cute puppy, dog reaction, kitten, golden retriever, pets being weird 등
   - 음식: street food, giant steak, bbq, cheese pull, food asmr, mukbang, japanese food 등
2. `python3 scripts/video_collect.py meta URL ...` → 조회수·길이·업로드일·[중복] 확인
3. 조건 맞는 것만 `python3 scripts/video_collect.py get URL --cat 동물|음식 --title "클릭 유도 한글 제목" [--still]`
   - 동물은 `--still` → 짤 후보 3장 생성. 직접 보고 동물이 잘 나온 것만 남기고 나머지 삭제
   - 결과: `outputs/videos/날짜/카테고리_NN_제목_@출처계정.mp4` (720p H.264, X 업로드 호환, mp4 메타데이터에도 출처·원본 URL) + 출처 txt
4. 사용자에게 mp4·짤·txt 파일 전송

## 업로드 시 주의 (출처)
- 남의 영상이라 그대로 올리면 저작권 신고·계정 제재 위험이 있음
- 같이 저장되는 txt의 `출처: @계정`을 게시글에 표기하는 걸 권장

## 기술 메모
- 틱톡: yt-dlp가 주는 원본 스트림(format_note에 watermarked 없는 것) 사용 → 틱톡 로고·아이디 워터마크 없음
- 유튜브: 영상 서버(googlevideo) 접속 불가라 다운로드 안 됨 (조회수 조회만 가능)
- 동물 짤 전용 소스(레딧 등)는 환경 허용이 거부됨 → 지금은 영상에서 뽑은 장면을 짤로 사용

## 토큰 절약 실행 방식 (2026-11-26~, 3시간마다)
1. `python3 scripts/video_collect.py discover` → **웹 검색 없이** 검증된 계정(`data/creators.csv`, 받은 영상의 업로더가 자동 추가됨)의 최근 영상을 훑어 조건(길이·조회수 10만+·중복·AI 태그) 맞는 후보만 출력. 계정당 최대 2개.
2. 후보가 카테고리별 3개 미만일 때만 웹 검색 1~2번으로 새 계정 발굴 (다양성 유지용).
3. `get URL --cat ... --title "캡션 근거 한글 제목" [--still]` → 짤은 5장 중 선명한 3장 자동 보관.
4. `python3 scripts/video_collect.py sheet --out <스크래치>/sheet.jpg` → 새 짤 전부를 **이미지 1장**으로 묶어 확인, 동물 안 보이는 번호만 삭제.
5. 문제 있는 계정(짜깁기·광고·AI)은 `data/creators.csv`의 blocked 칸에 `y` 표시 → 다음부터 제외.

## 로컬 AI 검토 결과 (2026-11-26)
- 서버: CPU 4코어 / RAM 15GB / GPU 없음. ollama·huggingface 접속 차단 → 현재 로컬 모델 사용 불가.
- 선명도 기반 짤 자동 선택만으로는 동물 없는 장면이 뽑히는 경우가 있어 최종 확인은 sheet 1장으로 함.
