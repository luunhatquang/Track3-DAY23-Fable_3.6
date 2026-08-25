# AI File Ownership & Dependency Map

File này dành cho AI coding agent và thành viên mới. Mục tiêu là giúp agent hiểu cấu trúc repo, đọc đúng thứ tự, chỉ sửa đúng phạm vi và không tạo conflict với nhánh khác.

## 1. Instructions for every AI agent

Trước khi sửa code:

1. Đọc `README.md`, `docs/LAB_GUIDE.md`, `docs/RUBRIC.md`, `docs/METRICS.md`.
2. Đọc `docs/team_plan/README.md`.
3. Đọc file nhiệm vụ tương ứng với role được giao.
4. Đọc bảng ownership trong file này.
5. Kiểm tra `git status --short` và branch hiện tại.
6. Chỉ sửa file thuộc owner của role.
7. Nếu cần thay đổi contract/file ngoài scope, dừng phần đó và gửi handoff request cho owner.
8. Không tự ý refactor hoặc format file của role khác.
9. Chạy test nhỏ nhất liên quan trước, sau đó mới chạy suite rộng.
10. Khi bàn giao, ghi rõ file đã sửa, command đã chạy, test result và blocker còn lại.

## 2. Repository map và owner

```text
Track3-DAY23-Fable_3.6/
├── README.md                                  [P3] shared documentation
├── pyproject.toml                             [P3] dependencies/tool config
├── Makefile                                   [P3] quality/run commands
├── Dockerfile                                 [P3] container runtime
├── docker-compose.yml                         [P3] optional Postgres service
├── .env.example                               [P3] safe environment template
├── .github/workflows/ci.yml                   [P3] CI gates
│
├── configs/                                   [P3]
│   ├── lab.yaml                               local scenario config
│   └── grading.yaml                           hidden grading config reference
│
├── data/
│   └── sample/scenarios.jsonl                 [READ-ONLY/P3] canonical samples
│
├── docs/
│   ├── LAB_GUIDE.md                           [READ-ONLY] assignment reference
│   ├── METRICS.md                             [READ-ONLY] metrics contract
│   ├── RUBRIC.md                              [READ-ONLY] grading contract
│   ├── DEMO_GUIDE.md                          [P4] demo runbook
│   └── team_plan/
│       ├── README.md                          [COORDINATION]
│       ├── PERSON_1_CORE_GRAPH.md             [P1 plan]
│       ├── PERSON_2_LLM_BACKEND.md            [P2 plan]
│       ├── PERSON_3_PERSISTENCE_QA.md         [P3 plan]
│       ├── PERSON_4_UI_UX_DEMO.md             [P4 plan]
│       └── AI_FILE_OWNERSHIP_MAP.md           [COORDINATION]
│
├── src/langgraph_agent_lab/
│   ├── __init__.py                            [P3]
│   ├── state.py                               [P1] state/reducers/contracts
│   ├── routing.py                             [P1] conditional route decisions
│   ├── graph.py                               [P1] node registration/edges/compile
│   ├── llm.py                                 [P2] provider factory/.env
│   ├── nodes.py                               [P2] all node behavior
│   ├── persistence.py                         [P3] memory/sqlite checkpointers
│   ├── metrics.py                             [P3] metric schemas/aggregation
│   ├── scenarios.py                           [P3] scenario validation/loading
│   ├── cli.py                                 [P3] orchestration entrypoint
│   └── report.py                              [P3] markdown report rendering
│
├── tests/
│   ├── test_state.py                          [P1]
│   ├── test_routing.py                        [P1]
│   ├── test_graph_structure.py                [P1, new]
│   ├── test_nodes.py                          [P2, new]
│   ├── fixtures/                              [P2]
│   ├── test_metrics.py                        [P3]
│   ├── test_graph_smoke.py                    [P3 integration]
│   ├── test_persistence.py                    [P3, new]
│   ├── test_cli.py                            [P3, new]
│   ├── test_scenarios.py                      [P3, new]
│   └── test_ui_helpers.py                     [P4, new]
│
├── ui/                                        [P4, new]
│   ├── streamlit_app.py                       UI entrypoint/orchestration
│   ├── components.py                          rendering helpers
│   ├── styles.css                             scoped UI tokens/styles
│   └── README.md                              UI-specific instructions
│
├── reports/
│   ├── lab_report_template.md                 [READ-ONLY] reference template
│   ├── lab_report.md                          [P3] final generated/edited report
│   └── evidence/
│       ├── graph.mmd                          [P1]
│       └── ui/                                [P4] screenshots
│
└── outputs/
    └── metrics.json                           [P3] generated grading artifact
```

## 3. Module dependency graph

```text
state.py [P1]
   ├── nodes.py [P2]
   ├── routing.py [P1]
   ├── graph.py [P1]
   ├── scenarios.py [P3]
   └── metrics.py [P3]

llm.py [P2]
   └── nodes.py [P2]

nodes.py [P2] + routing.py [P1] + state.py [P1]
   └── graph.py [P1]

persistence.py [P3]
   └── cli.py [P3] ── build_graph() [P1]

scenarios.py [P3] ── initial_state() [P1]
   └── cli.py [P3]

graph.py + persistence.py + metrics.py + report.py
   └── cli.py [P3]

compiled graph + checkpointer + metrics
   └── ui/streamlit_app.py [P4]
```

Ý nghĩa:

- `state.py` là contract upstream quan trọng nhất; freeze đầu tiên.
- `nodes.py` và `routing.py` có thể làm song song sau khi state contract ổn định.
- `graph.py` cần node names nhưng không sở hữu node implementation.
- `cli.py` là integration point, chỉ Người 3 chỉnh.
- UI chỉ consume public backend contract, không import private helper để tái tạo routing.

## 4. Runtime data flow

```text
scenarios.jsonl
    ↓ load_scenarios()
Scenario
    ↓ initial_state()
AgentState + unique thread_id
    ↓ graph.invoke(state, config)
START → intake → classify
    ├─ simple → answer → finalize → END
    ├─ tool → tool → evaluate → answer/retry
    ├─ missing_info → clarify → finalize → END
    ├─ risky → risky_action → approval → tool/clarify
    └─ error → retry → tool/dead_letter
    ↓
final AgentState
    ├─ metric_from_state()
    ├─ outputs/metrics.json
    ├─ reports/lab_report.md
    └─ Streamlit timeline/metrics/history
```

## 5. State contract

| Field | Type intent | Update | Producer | Consumers |
|---|---|---|---|---|
| `thread_id` | string | overwrite/init | `initial_state` | CLI, checkpointer, UI |
| `scenario_id` | string | overwrite/init | `initial_state` | metrics, report |
| `query` | string | overwrite | initial/intake | classify, answer, UI |
| `route` | route string | overwrite | classify | routing, tool, metrics, UI |
| `risk_level` | string | overwrite | classify | risky node, approval UI |
| `attempt` | integer | overwrite | initial/retry | tool, retry routing, metrics |
| `max_attempts` | integer | overwrite/init | initial/UI | retry routing |
| `should_retry` | boolean | overwrite/init | initial | tool/test behavior if used |
| `evaluation_result` | string | overwrite | evaluate | evaluate routing |
| `pending_question` | optional string | overwrite | clarify | metrics, UI |
| `proposed_action` | optional string | overwrite | risky_action | approval, UI |
| `approval` | optional mapping | overwrite | approval | approval routing, answer, metrics, UI |
| `final_answer` | optional string | overwrite | answer/clarify/dead_letter | metrics, report, UI |
| `messages` | list string | append | nodes | audit/debug |
| `tool_results` | list string | append | tool | evaluate, answer, UI |
| `errors` | list string | append | retry/dead-letter | metrics, report, UI |
| `events` | list mapping | append | every node | metrics, timeline, report |

Không được đổi tên field mà chưa cập nhật owner/consumers qua handoff có kiểm soát.

## 6. Node I/O map

| Node | Reads | Writes | Next decision |
|---|---|---|---|
| `intake` | query | normalized query, messages, events | fixed classify |
| `classify` | query | route, risk_level, events | route_after_classify |
| `tool` | route, attempt, query, proposed_action | tool_results, events | fixed evaluate |
| `evaluate` | tool_results | evaluation_result, events | route_after_evaluate |
| `answer` | query, tool_results, approval | final_answer, events | fixed finalize |
| `clarify` | query, approval | pending_question, final_answer, events | fixed finalize |
| `risky_action` | query, risk_level | proposed_action, events | fixed approval |
| `approval` | proposed_action, query | approval, events | route_after_approval |
| `retry` | attempt, errors | attempt, errors, events | route_after_retry |
| `dead_letter` | attempt, errors, query | final_answer, events | fixed finalize |
| `finalize` | state summary | events | END |

## 7. Parallel execution map

Có thể làm song song sau state contract:

```text
P1: routing + graph topology
P2: llm + node implementations
P3: persistence + metrics + report renderer
P4: UI components với contract fixtures
```

Không được làm song song trên cùng file:

- P1 và P2 không cùng sửa `state.py`.
- P1 và P3 không cùng sửa `graph.py`.
- P2 và P3 không cùng sửa `llm.py`.
- P3 và P4 không cùng sửa `pyproject.toml`, `README.md` hoặc report.
- P1 và P4 không cùng ghi một evidence path.

## 8. Handoff request format

Khi agent cần owner khác sửa file, gửi yêu cầu theo mẫu:

```markdown
### Handoff request
- From role: P?
- To owner: P?
- File owned by receiver:
- Current behavior:
- Required behavior:
- Input/output contract:
- Reproduction/test command:
- Blocking or non-blocking:
- Deadline/merge dependency:
```

Không gửi yêu cầu chung chung như “sửa backend để UI chạy”. Phải có reproduction và contract mong muốn.

## 9. Merge order và dependency gates

### Gate 1 — State contract

Merge P1 state commit trước. P2/P3/P4 rebase đúng contract.

### Gate 2 — Core behavior

Merge P1 routing/graph và P2 nodes/LLM. Chạy state, routing, node tests.

### Gate 3 — Integration backend

Merge P3 persistence/metrics/CLI. Chạy sample scenarios và recovery tests.

### Gate 4 — UI

P4 rebase lên backend integration, kết nối invoke/interrupt/resume thật, sau đó merge UI.

### Gate 5 — Release

P3 chạy formatting/quality gates, generate metrics/report; P4 chụp evidence từ final commit.

## 10. Conflict-resolution protocol

Nếu phát hiện hai branch cùng sửa một file:

1. Không auto-resolve bằng cách giữ cả hai phiên bản.
2. Xác định owner theo map này.
3. Owner quyết định nội dung cuối của file.
4. Non-owner tách logic cần giữ thành handoff request hoặc commit riêng không đụng file đó.
5. Chạy lại test liên quan trực tiếp và integration test.
6. Ghi quyết định contract vào PR/commit message nếu ảnh hưởng consumer khác.

Nếu conflict nằm trong generated file như metrics/report/evidence, regenerate từ final integrated code thay vì ghép thủ công.

## 11. AI completion report format

Mỗi AI agent kết thúc task bằng báo cáo:

```markdown
## Completed
- Files changed:
- Behaviors implemented:
- Contract assumptions:

## Verification
- Command:
- Result:

## Handoff
- Commit/branch:
- Files requested from another owner:
- Known risks/blockers:
```

Agent không được tuyên bố hoàn thành nếu test chưa chạy; phải ghi rõ `not run` và lý do nếu bị chặn.

## 12. Final release checklist

- [ ] Không còn `TODO(student)`/`NotImplementedError` trong core deliverable.
- [ ] Không có hard-coded scenario IDs/answers.
- [ ] Structured-output LLM classification hiện diện trong code.
- [ ] Grounded LLM answer hiện diện trong code.
- [ ] Mọi graph path qua finalize và END.
- [ ] Retry bounded.
- [ ] Risky path qua approval.
- [ ] Real HITL approve/reject/resume demo được.
- [ ] SQLite recovery/history có evidence.
- [ ] Metrics schema hợp lệ và sample success đạt mục tiêu.
- [ ] Report đầy đủ.
- [ ] UI accessibility/responsive smoke check đạt.
- [ ] Test, lint, typecheck, run-scenarios, grade-local pass.
- [ ] Không có secret, DB, cache hoặc debug artifact nhạy cảm trong git.

