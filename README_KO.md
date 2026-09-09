# KPOP Corea MX — GitHub Actions 자동 Reel 렌더러 v2.1

무료 GitHub Actions + FFmpeg로 @kpopcoreamx용 Instagram Reel MP4를 자동 생성한다.

## v2.1 핵심 개선
- Mexico-first Hook
- 큰 검은 카드 제거 → 하단 반투명 그라데이션
- 사진이 화면의 주인공이 되도록 텍스트 면적 축소
- 가로/단체 사진은 contain + 블러 배경으로 멤버 잘림 최소화
- 세로/솔로 사진은 cover 사용
- 장면별 fit_mode / focus_x / focus_y / zoom / pan_x / pan_y 조정 가능
- @kpopcoreamx는 한 번만 표시
- 하단 Instagram UI 안전영역 고려
- `data/render_request.json` 변경 시 자동 렌더

## 핵심 파일
- `.github/workflows/render-reel.yml` — 자동 렌더 workflow
- `scripts/render_reel.py` — FFmpeg/Pillow 렌더 엔진
- `data/render_request.json` — ChatGPT가 갱신하는 최종 Reel 입력
- `requirements.txt`

## 자동 흐름
1. ChatGPT가 최신 K-pop 뉴스 조사·검증
2. 점수가 충분한 뉴스만 선정
3. 실제 사진 URL과 스페인어 자막을 `data/render_request.json`에 기록
4. GitHub Actions가 자동 시작
5. 1080×1920 / H.264 / 30fps MP4 생성
6. `reel-output` Artifact에 저장
7. 사용자는 Instagram에서 음악만 추가해 게시

## 장면 예시
```json
{
  "image_url": "https://...",
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
