# KPOP Corea MX — Reel Scout v3.0 + Renderer v2.2

@kpopcoreamx용 Instagram Reel 자동화 시스템. 목표는 단순 조회수가 아니라 **멕시코 K-pop 팬의 팔로우 전환**이다.

## 현재 구조
- **Reel Scout v3.0**: 뉴스 조사, 사실검증, 후보 점수화, 5종 Hook 경쟁, Mexico Utility, Follow Score, 다양성 감점, 성과 학습
- **Renderer v2.2**: 실제 사진 검증, 5컷 6~8초 MP4 렌더, 커버 생성, ffprobe 품질검증

## v3.0 핵심 개선
1. **5종 Hook 경쟁**
   - MEXICO_UTILITY
   - HARD_NUMBER
   - FOMO_URGENCY
   - FAN_IDENTITY
   - CURIOSITY_CONTRAST
   - 각 Hook을 100점으로 평가해 1개 승자를 선택하고 winning_hook_type을 기록

2. **Mexico Utility Score (15점)**
   - 멕시코 팬에게 실제 행동 가능한 정보인지 평가
   - 티켓, 현지 일정, 공연장, 현지시간, 판매처, 스트리밍 시간 등의 가치에 높은 점수

3. **Follow Score (15점)**
   - 한 번 보고 끝나는 뉴스보다 ‘앞으로도 이 계정을 팔로우할 이유’가 있는 소재를 우선
   - 티켓 변화, 후속 일정, 현지 업데이트, 지속 추적 가능한 주제가 높은 점수

4. **콘텐츠 다양성 감점 (최대 -10)**
   - 같은 아티스트, 같은 topic_type, 같은 Hook 방식이 반복되면 감점
   - 단, 매우 중요한 멕시코 직접 뉴스는 감점을 제한

5. **성과 기반 학습**
   - performance_history.json의 최근 성과를 기반으로 skip rate, 평균시청시간, 공유, 댓글, 프로필 방문, 팔로우 전환을 학습
   - 최소 3개 Reel이 쌓이기 전에는 과적합하지 않음

## v3.0 점수 구조
100점 base_score:
- freshness 15
- mexico_relevance 15
- mexico_utility 15
- mexico_fandom_interest 10
- winning_hook 15
- follow_score 15
- share_potential 5
- comment_potential 5
- visual_strength 5

최종점수:
`final_score = min(100, base_score + performance_adjustment) - diversity_penalty`

기본 제작 기준은 final_score **88점 이상**.

## 운영 시간
- 04:00 KST — 조사/후보 누적
- 10:00 KST — 최종 선정 및 자동 제작
- 12:30 KST — 사용자 게시 목표시간 (= 21:30 CDMX)
- 16:00 KST — 조사/후보 누적
- 22:00 KST — 조사/후보 누적

공식 확인된 멕시코 직접 관련 속보가 96점 이상이면 조사 회차에서도 즉시 제작할 수 있다.

## 데이터 파일
- `data/strategy_config.json` — v3.0 점수, Hook, 다양성, 학습 규칙의 기준 파일
- `data/candidate_state.json` — 현재 멕시코 날짜의 후보 최대 5개와 v3.0 점수/Hook 경쟁 결과
- `data/render_history.json` — 최근 생성 Reel 이력 및 중복/다양성 판단
- `data/performance_history.json` — 사용자가 제공한 Instagram Insights 기반 성과 학습 데이터
- `data/render_request.json` — 최종 선택 Reel의 렌더 입력

## 렌더러 v2.2 기능
- 1080×1920 / 9:16 / 30fps / H.264
- 정확히 5컷, 총 6~8초
- 첫 Hook 0.5~0.9초
- 실제 이미지 MIME/용량/최소 해상도 검사
- 외부 이미지 다운로드 재시도
- 단체/가로 사진: contain + 블러 배경
- 세로/솔로 사진: cover
- focus_x / focus_y / zoom 지원
- 큰 검은 카드 대신 하단 반투명 그라데이션
- @kpopcoreamx는 마지막 컷에 1회만 표시
- 완성 후 ffprobe로 H.264 / 1080×1920 / 길이 검사
- MP4 + Cover JPG + Manifest JSON 생성

## 최종 운영 흐름
1. Scout가 최신 뉴스 조사와 교차검증
2. 각 후보에 Mexico Utility / Follow Score 포함 v3.0 점수 계산
3. 후보마다 서로 다른 5종 Hook 생성 및 경쟁
4. render_history를 보고 다양성 감점
5. performance_history가 충분하면 성과 보정
6. final_score로 최종 후보 선정
7. 렌더 직전 시간 민감 사실 재검증
8. 최신 실제 사진 5장 선정
9. `data/render_request.json` 업데이트
10. GitHub Actions 자동 렌더
11. MP4 + Cover + Manifest 검증
12. 사용자는 Instagram에서 음악을 추가하고 12:30 KST에 직접 게시
13. 12~24시간 뒤 Insights를 performance_history에 반영해 다음 Reel 개선

새 무료 도구를 더 붙이기보다, 현재는 이 의사결정·학습 엔진을 실제 게시 성과로 계속 보정하는 것이 우선이다.
