# KPOP Corea MX — GitHub Actions 자동 Reel 렌더러

이 폴더는 **무료 GitHub Actions + FFmpeg**로 Instagram Reel MP4를 자동 생성하는 시작 패키지다.

## 이 구조가 하는 일
- 6시간마다 또는 수동 실행
- `data/*.json` 페이로드를 읽음
- 실제 사진 URL 5장을 다운로드
- 1080x1920 세로 비디오로 자동 크롭
- 각 장면에 Zoom/Pan(Ken Burns) 적용
- 장면별 스페인어 헤드라인/서브헤드라인 표시
- 5개 장면을 이어붙여 최종 MP4 생성
- 생성된 MP4를 GitHub Actions Artifact로 저장

## 핵심 파일
- `.github/workflows/render-reel.yml` — GitHub Actions 워크플로우
- `scripts/render_reel.py` — FFmpeg 렌더 스크립트
- `data/sample_payload.json` — 샘플 입력 데이터

## 사용 방법
1. 이 폴더를 새 GitHub 저장소에 업로드
2. GitHub 저장소의 **Actions** 탭으로 이동
3. `Render K-pop Reel` 워크플로우 실행
4. 실행이 끝나면 **Artifacts**에서 MP4 다운로드

## 페이로드 형식
```json
{
  "slug": "2026-09-08_skz_straycity_cdmx",
  "brand": "@kpopcoreamx",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "scenes": [
    {
      "image_url": "https://...",
      "duration": 0.8,
      "headline": "STRAYCITY\\nARRANCA MAÑANA",
      "subheadline": "LATINOAMÉRICA"
    }
  ]
}
```

## 다음 단계 추천
이제 다음 자동화를 추가하면 된다.
1. ChatGPT가 뉴스/자막/사진 URL 패키지를 생성
2. 그 JSON을 GitHub 저장소에 저장하거나 교체
3. GitHub Actions가 MP4를 렌더
4. 네가 Instagram에서 음악만 넣고 업로드
