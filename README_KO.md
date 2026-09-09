# KPOP Corea MX — GitHub Actions 자동 Reel 렌더러 v2.2

무료 GitHub Actions + FFmpeg로 @kpopcoreamx용 Instagram Reel MP4를 자동 생성한다.

## v2.2 핵심 개선
- Mexico-first Hook 유지
- 큰 검은 카드 제거 → 하단 반투명 그라데이션
- 가로/단체 사진은 contain + 블러 배경으로 멤버 잘림 최소화
- 세로/솔로 사진은 cover 사용
- 장면별 fit_mode / focus_x / focus_y / zoom / pan_x / pan_y 조정 가능
- 외부 이미지 URL 다운로드 3회 재시도
- 이미지 MIME/용량/최소 해상도 검증
- 정확히 5컷, 총 6~8초, 첫 훅 0.5~0.9초 자동 검증
- MP4 생성 후 ffprobe로 H.264 / 1080x1920 / 길이 자동 검증
- MP4뿐 아니라 커버 JPG와 manifest JSON도 같이 생성
- 렌더 동시 실행 충돌 방지(concurrency)
- Artifact 14일 보관
- `data/render_request.json` 변경 시에만 자동 렌더
- `data/candidate_state.json`으로 같은 날 후보 상태 보존
- `data/render_history.json`으로 최근 생성 주제 중복 방지

## 핵심 파일
- `.github/workflows/render-reel.yml` — 자동 렌더 workflow
- `scripts/render_reel.py` — FFmpeg/Pillow 렌더 엔진
- `data/render_request.json` — ChatGPT가 갱신하는 최종 Reel 입력
- `data/candidate_state.json` — 하루 후보 기록
- `data/render_history.json` — 생성 이력/중복 방지
- `requirements.txt`

## 자동 흐름
1. Reel Scout가 최신 K-pop 뉴스 조사·검증
2. 후보를 candidate_state에 누적
3. 최근 render_history와 비교해 같은 주제 반복 생성 방지
4. 충분히 강한 뉴스만 선택
5. 실제 사진 URL과 스페인어 자막을 `data/render_request.json`에 기록
6. GitHub Actions 자동 시작
7. 사진과 입력값을 검증한 뒤 1080×1920 / H.264 / 30fps MP4 생성
8. ffprobe로 최종 MP4 자동 검사
9. MP4 + Cover JPG + Manifest JSON을 `reel-output` Artifact에 저장
10. 사용자는 Instagram에서 음악만 추가해 게시

## 장면 예시
```json
{
  "image_url": "https://...",
  "source_url": "https://official-source.example/...",
  "image_credit": "Official artist account",
  "duration": 0.7,
  "headline": "¡POCOS BOLETOS!",
  "subheadline": "STRAY KIDS EN CDMX",
  "fit_mode": "contain",
  "focus_x": 0.5,
  "focus_y": 0.35,
  "zoom": 1.10
}
```

`fit_mode`는 `auto`, `contain`, `cover`를 사용할 수 있다. 단체/가로 사진에는 `contain`, 세로 인물 사진에는 `cover`가 기본적으로 유리하다.
