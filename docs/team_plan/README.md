# Kế hoạch làm việc nhóm — LangGraph Agent Lab

Tài liệu này là điểm bắt đầu bắt buộc cho cả bốn thành viên và mọi AI agent tham gia dự án. Mục tiêu là hoàn thành toàn bộ rubric, có backend chạy ổn định, có UI/UX để demo, có persistence/recovery evidence và hạn chế tối đa merge conflict.

## 1. Mục tiêu chung

Sản phẩm cuối ngày phải đáp ứng:

- LangGraph có typed state, reducers và 11 nodes.
- Phân loại intent và sinh câu trả lời bằng LLM thật.
- Đủ năm route: `simple`, `tool`, `missing_info`, `risky`, `error`.
- Retry loop có giới hạn và dead-letter path.
- Risky action phải đi qua approval; UI hỗ trợ pause/resume thật.
- Có Memory và SQLite checkpointer, state history hoặc resume evidence.
- Bảy sample scenarios chạy đúng; có thêm edge-case tests.
- `outputs/metrics.json` hợp lệ và `reports/lab_report.md` đầy đủ.
- Có Streamlit UI để chạy ticket, approve/reject, xem timeline và metrics.
- `test`, `lint`, `typecheck`, `run-scenarios`, `grade-local` đều đạt.

## 2. Phân công và tài liệu bắt buộc

| Người | Vai trò | Tài liệu phải đọc |
|---|---|---|
| Người 1 | State, routing, graph architecture | [PERSON_1_CORE_GRAPH.md](PERSON_1_CORE_GRAPH.md) |
| Người 2 | LLM integration và backend nodes | [PERSON_2_LLM_BACKEND.md](PERSON_2_LLM_BACKEND.md) |
| Người 3 | Persistence, metrics, QA, report, integration | [PERSON_3_PERSISTENCE_QA.md](PERSON_3_PERSISTENCE_QA.md) |
| Người 4 | Streamlit UI/UX và demo | [PERSON_4_UI_UX_DEMO.md](PERSON_4_UI_UX_DEMO.md) |

Mọi người và mọi AI agent đều phải đọc thêm [AI_FILE_OWNERSHIP_MAP.md](AI_FILE_OWNERSHIP_MAP.md) trước khi sửa file.

## 3. Coverage theo rubric

| Rubric | Điểm | Owner chính | Owner hỗ trợ |
|---|---:|---|---|
| Architecture & state schema | 15 | Người 1 | Người 2 |
| Graph construction & wiring | 15 | Người 1 | Người 2 |
| LLM integration | 15 | Người 2 | Người 3 |
| Graph behavior | 20 | Người 2 | Người 1, Người 3 |
| Persistence & recovery | 10 | Người 3 | Người 4 |
| Metrics & tests | 15 | Người 3 | Người 1, Người 2 |
| Report & demo | 10 | Người 3, Người 4 | Người 1, Người 2 |
| Bonus extensions | Bonus/90+ | Người 3, Người 4 | Người 1 |

Các extension mục tiêu:

1. SQLite persistence và state-history replay.
2. Real HITL bằng `interrupt()` và `Command(resume=...)`.
3. Streamlit approval/observability UI.
4. Mermaid graph diagram.
5. LLM-as-judge nếu còn thời gian.

## 4. Contract phải được freeze trước khi code song song

Người 1 tạo commit state contract đầu tiên. Sau commit này, chỉ Người 1 được sửa `state.py`, trừ khi cả nhóm đồng ý chuyển ownership.

### Node names cố định

```text
intake
classify
tool
evaluate
answer
clarify
risky_action
approval
retry
dead_letter
finalize
```

### State keys cố định

```text
thread_id
scenario_id
query
route
risk_level
attempt
max_attempts
should_retry
evaluation_result
pending_question
proposed_action
approval
final_answer
messages
tool_results
errors
events
```

### Reducer contract

| Field | Cách cập nhật |
|---|---|
| `messages` | append-only |
| `tool_results` | append-only |
| `errors` | append-only |
| `events` | append-only |
| Các field còn lại | overwrite |

### Approval contract

```python
{
    "approved": bool,
    "reviewer": str,
    "comment": str,
}
```

### Event contract

```python
{
    "node": str,
    "event_type": str,
    "message": str,
    "latency_ms": int,
    "metadata": dict,
}
```

## 5. Quy tắc branch và commit

| Người | Branch |
|---|---|
| Người 1 | `feat/core-graph` |
| Người 2 | `feat/llm-nodes` |
| Người 3 | `feat/observability-qa` |
| Người 4 | `feat/demo-ui` |

Quy tắc:

- Tất cả branch bắt đầu từ cùng một commit nền.
- Không sửa file thuộc owner khác để “sửa nhanh”.
- Nếu cần thay đổi contract, tạo yêu cầu handoff cho owner, nêu rõ input/output mong muốn.
- Commit nhỏ, mỗi commit chỉ giải quyết một nhóm hành vi.
- Không chạy auto-format toàn repo trên branch cá nhân.
- Không commit `.env`, API key, SQLite database, cache hoặc log chứa dữ liệu nhạy cảm.
- Chỉ Người 3 sửa dependency/config/CI/shared documentation.
- Generated evidence UI thuộc Người 4; báo cáo tổng hợp thuộc Người 3.

## 6. Timeline trong ngày

### T+0 đến T+30 phút — Freeze contract

- Người 1: state schema, node names, routing outputs.
- Người 2: structured-output schema và node output contract.
- Người 3: environment, dependency và command gates.
- Người 4: wireframe và API cần dùng từ graph.

### T+30 phút đến T+3 giờ — Parallel implementation

- Người 1 làm state/routing/graph.
- Người 2 làm LLM/nodes/tests.
- Người 3 làm SQLite/metrics/report/tests.
- Người 4 làm UI với fixture/mock state đúng contract.

### T+3 đến T+4 giờ — Integration lần 1

Merge logic theo thứ tự:

1. State contract và core graph.
2. LLM nodes.
3. Persistence/metrics/CLI.
4. UI kết nối backend thật.

### T+4 đến T+6 giờ — Extensions và hardening

- Real interrupt/resume.
- SQLite history/resume.
- Hidden-style scenarios.
- Metrics dashboard và Mermaid diagram.

### T+6 đến T+8 giờ — QA, report và rehearsal

- Chạy toàn bộ quality gates.
- Chụp evidence.
- Hoàn thành báo cáo.
- Demo từ clean environment.

## 7. Quality gates chung

```bash
make test
make lint
make typecheck
make run-scenarios
make grade-local
streamlit run ui/streamlit_app.py
```

Không được xem là hoàn thành nếu chỉ chạy được trên máy của một thành viên hoặc chỉ pass sample bằng keyword hard-code.

## 8. Kịch bản demo cuối

1. Simple query đi thẳng tới answer.
2. Tool lookup hiển thị tool result và grounded answer.
3. Risky refund/delete dừng tại approval.
4. Approve rồi resume đúng thread.
5. Reject rồi chuyển sang clarification.
6. Timeout chạy retry loop và hồi phục.
7. Unrecoverable scenario đi vào dead letter.
8. Xem metrics dashboard.
9. Xem SQLite state history/resume evidence.
10. Trình bày Mermaid graph diagram và failure analysis.

