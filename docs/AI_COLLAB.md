# AI Collaboration (MCP)

- 작업 전 `CheckList.md`의 현재 단계/DoD 확인 → 할 일 요약 생성
- MCP 서버: filesystem/git/shell/http 사용
- AI가 수정 가능한 경로: `.mcp/servers.json`의 `allowWrite`
- 데이터/시크릿은 `denyWrite` (수정 불가)
- PR 제목: `feat|fix|chore(scope): summary`
- 모델 승격/롤백: `/promote` API만 사용
