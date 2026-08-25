# Người 2 — LLM & Backend Behavior Engineer

## 1. Mission

Chịu trách nhiệm toàn bộ hành vi bên trong graph: LLM classification, grounded answer, mock tool, evaluation, clarification, risky action, approval, retry, dead letter và audit events. Code phải hoạt động với hidden queries, không hard-code scenario và có thể test offline bằng mock LLM.

Branch: `feat/llm-nodes`

## 2. File ownership

Được sửa:

```text
src/langgraph_agent_lab/llm.py
src/langgraph_agent_lab/nodes.py
tests/test_nodes.py                    # tạo mới
tests/fixtures/                        # tạo mới nếu cần cho fake LLM
```

Không được sửa:

```text
src/langgraph_agent_lab/state.py
src/langgraph_agent_lab/routing.py
src/langgraph_agent_lab/graph.py
src/langgraph_agent_lab/persistence.py
src/langgraph_agent_lab/metrics.py
src/langgraph_agent_lab/cli.py
pyproject.toml
configs/
ui/
reports/lab_report.md
```

Dependency mới phải gửi cho Người 3 thêm vào `pyproject.toml`.

## 3. Contract với các thành viên khác

Đọc state contract của Người 1 trước khi implement. Node chỉ nhận `AgentState` và trả partial state update; không mutate input.

Mỗi node phải trả event có `node` trùng tên node đã đăng ký:

| Function | Event node | Output chính |
|---|---|---|
| `classify_node` | `classify` | `route`, `risk_level` |
| `tool_node` | `tool` | `tool_results` |
| `evaluate_node` | `evaluate` | `evaluation_result` |
| `answer_node` | `answer` | `final_answer` |
| `ask_clarification_node` | `clarify` | `pending_question`, `final_answer` |
| `risky_action_node` | `risky_action` | `proposed_action` |
| `approval_node` | `approval` | `approval` |
| `retry_or_fallback_node` | `retry` | `attempt`, `errors` |
| `dead_letter_node` | `dead_letter` | `final_answer`, `errors` nếu cần |
| `finalize_node` | `finalize` | audit event |

## 4. Work package A — LLM factory

Checklist:

- [ ] Nạp `.env` bằng `load_dotenv()` trước khi kiểm tra key.
- [ ] Provider priority rõ ràng: Gemini, OpenAI, Anthropic hoặc theo contract hiện tại.
- [ ] Model override qua `LLM_MODEL` và tham số `model`.
- [ ] Temperature mặc định `0.0` cho classification ổn định.
- [ ] Báo thiếu package/provider bằng error có hướng dẫn cài.
- [ ] Không log hoặc trả API key trong exception.
- [ ] Có return type hợp lý để lint/typecheck không thất bại.

Gửi dependency request cho Người 3:

```text
python-dotenv
langchain-google-genai hoặc provider được nhóm chọn
```

## 5. Work package B — Structured classification

Tạo Pydantic model hoặc TypedDict cho structured output. Chỉ cho phép:

```text
simple, tool, missing_info, risky, error
```

Prompt phải mô tả:

- `risky`: refund, delete, cancel, send email, thay đổi dữ liệu hoặc side effect.
- `tool`: lookup/search/tracking chỉ đọc thông tin.
- `missing_info`: yêu cầu quá mơ hồ, thiếu đối tượng hoặc context hành động.
- `error`: timeout, crash, unavailable, system failure.
- `simple`: câu hỏi chung không cần tool hoặc side effect.
- Priority khi query chứa nhiều intent: `risky > tool > missing_info > error > simple`.

Checklist:

- [ ] Gọi `get_llm().with_structured_output(...)` thật.
- [ ] Không dùng exact query matching.
- [ ] Không đọc `scenario_id` để quyết định route.
- [ ] `risk_level="high"` chỉ cho risky, còn lại low.
- [ ] Có defensive handling nếu structured call lỗi; fallback không được che giấu lỗi trong production log.
- [ ] Event metadata có thể chứa model/route nhưng không chứa secret.

## 6. Work package C — Tool, evaluate và retry behavior

`tool_node`:

- Đọc `attempt`.
- Route `error` và `attempt < 2` trả result chứa `ERROR`.
- Các trường hợp khác trả mock success có liên hệ với query/proposed action.
- Append đúng một tool result mỗi lần gọi.

`evaluate_node`:

- Đọc tool result mới nhất.
- Empty/missing/`ERROR` -> `needs_retry`.
- Valid result -> `success`.
- Bonus: LLM-as-judge với structured output; phải có heuristic fallback để demo không đổ nếu judge call lỗi.

`retry_or_fallback_node`:

- Tăng attempt đúng một lần.
- Append lỗi có attempt number.
- Không tự quyết định node tiếp theo; routing thuộc Người 1.

`dead_letter_node`:

- Trả final answer rõ ràng, không giả thành công.
- Cho biết request đã được dừng/escalate sau số lần thử.

## 7. Work package D — Answer, clarification và risky flow

`answer_node`:

- Dùng LLM thật.
- Prompt gồm query, latest/all relevant tool results, approval và proposed action.
- Không nói tool đã thực hiện nếu không có tool result thành công.
- Với simple route, trả câu trả lời hữu ích nhưng không bịa policy nội bộ.
- Với risky route, phản ánh approval và kết quả action.

`ask_clarification_node`:

- Tạo câu hỏi cụ thể dựa trên phần thiếu của query.
- Ghi cùng nội dung vào `pending_question` và `final_answer` để CLI và UI đều hiển thị được.
- Không gọi tool khi chưa đủ dữ liệu.

`risky_action_node`:

- Mô tả hành động, target, side effect và lý do cần approval.
- Không thực hiện action tại node này.

## 8. Work package E — HITL approval

Chế độ mặc định cho test/CLI:

```python
{"approved": True, "reviewer": "mock-reviewer", "comment": "auto-approved for lab"}
```

Khi `LANGGRAPH_INTERRUPT=true`:

- Gọi `interrupt()` với payload serializable gồm query, proposed action và thread/scenario context.
- Khi resume, validate decision theo approval contract.
- Rejected phải để routing chuyển sang clarification.
- Không phát sinh duplicate side effect khi node được replay.

Phối hợp Người 4 để thử:

```python
Command(resume={"approved": True, "reviewer": "...", "comment": "..."})
```

## 9. Work package F — Unit tests

Không gọi API thật trong unit test. Dùng monkeypatch/fake model để kiểm tra:

- [ ] Structured classification cho đủ năm route.
- [ ] Composite query ưu tiên risky.
- [ ] Hidden-style wording không dựa exact sample.
- [ ] Tool error ở attempt 0/1 và success ở attempt 2.
- [ ] Evaluate empty/error/success.
- [ ] Retry tăng counter và append error.
- [ ] Clarification có pending question.
- [ ] Risky node không chạy action.
- [ ] Approval mock và interrupted/resumed decision validation.
- [ ] Answer prompt chứa grounding context.
- [ ] Dead letter và finalize events.

## 10. Commit plan

1. `fix(llm): load environment and initialize providers safely`
2. `feat(nodes): add structured intent classification`
3. `feat(nodes): implement tool evaluation and retry events`
4. `feat(nodes): implement grounded response and clarification`
5. `feat(hitl): support mock and interrupt approval modes`
6. `test(nodes): add offline behavior coverage`

## 11. Definition of done

- Không còn `NotImplementedError` trong `nodes.py`.
- Classification và answer có LLM calls thật nhìn thấy rõ trong code.
- Unit tests không cần API key.
- Real provider smoke test chạy được khi có `.env` hợp lệ.
- Mọi node trả partial update đúng contract, không mutate state.
- Handoff cho Người 3 gồm provider đã dùng, model, commit hash và test commands.

