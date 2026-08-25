# Người 1 — Core Graph Architect

## 1. Mission

Chịu trách nhiệm thiết kế state contract, routing contract và topology của LangGraph. Kết quả phải tạo ra một graph compile được, mọi route kết thúc, retry có giới hạn và các module khác có interface ổn định để phát triển song song.

Branch: `feat/core-graph`

## 2. File ownership

Được sửa:

```text
src/langgraph_agent_lab/state.py
src/langgraph_agent_lab/routing.py
src/langgraph_agent_lab/graph.py
tests/test_state.py
tests/test_routing.py
tests/test_graph_structure.py       # tạo mới nếu cần
reports/evidence/graph.mmd          # Mermaid source, phối hợp Người 4 nếu có ảnh
```

Không được sửa:

```text
src/langgraph_agent_lab/nodes.py
src/langgraph_agent_lab/llm.py
src/langgraph_agent_lab/persistence.py
src/langgraph_agent_lab/metrics.py
src/langgraph_agent_lab/cli.py
src/langgraph_agent_lab/report.py
pyproject.toml
Makefile
ui/
reports/lab_report.md
```

Nếu cần thay đổi một file ngoài ownership, gửi yêu cầu cho owner thay vì tự sửa.

## 3. Dependencies và handoff

Đầu vào:

- Node names và partial-state outputs đã chốt với Người 2.
- Checkpointer object từ Người 3, truyền vào `build_graph(checkpointer=...)`.
- UI của Người 4 cần compiled graph có thể invoke/resume bằng cùng `thread_id`.

Đầu ra cho nhóm:

- Typed `AgentState` đã freeze.
- Bốn routing function ổn định.
- Compiled graph với checkpointer injection.
- Mermaid topology.
- Tests cho state/routing/structure.

## 4. Work package A — State schema

Checklist:

- [ ] Giữ `AgentState` lean và serializable.
- [ ] Bổ sung `evaluation_result: str`.
- [ ] Bổ sung `pending_question: str | None`.
- [ ] Bổ sung `proposed_action: str | None`.
- [ ] Bổ sung `approval` theo approval contract.
- [ ] Cân nhắc đưa `should_retry: bool` từ scenario vào state để hidden scenarios không mất dữ liệu.
- [ ] Giữ `messages`, `tool_results`, `errors`, `events` là append-only reducers.
- [ ] Các control fields dùng overwrite semantics.
- [ ] Khởi tạo đầy đủ field trong `initial_state()`.
- [ ] Không lưu LLM object, database connection hoặc object không serializable vào state.

Acceptance:

- `initial_state()` tạo thread ID riêng cho từng scenario.
- Không dùng mutable default dùng chung.
- Pydantic scenario validation vẫn hoạt động.
- State có thể checkpoint bằng MemorySaver và SQLiteSaver.

## 5. Work package B — Routing

Implement chính xác:

```text
route_after_classify:
  simple       -> answer
  tool         -> tool
  missing_info -> clarify
  risky        -> risky_action
  error        -> retry
  unknown      -> answer

route_after_evaluate:
  needs_retry  -> retry
  otherwise    -> answer

route_after_retry:
  attempt < max_attempts  -> tool
  attempt >= max_attempts -> dead_letter

route_after_approval:
  approved -> tool
  rejected/missing/malformed -> clarify
```

Defensive requirements:

- [ ] Không `KeyError` khi optional field bị thiếu.
- [ ] Ép/default hợp lý cho `attempt` và `max_attempts`.
- [ ] Approval malformed không được mặc định thành approved.
- [ ] Unknown route không tạo vòng lặp.

## 6. Work package C — Graph wiring

Đăng ký đủ 11 nodes:

```text
intake, classify, tool, evaluate, answer, clarify,
risky_action, approval, retry, dead_letter, finalize
```

Fixed edges:

```text
START -> intake
intake -> classify
tool -> evaluate
answer -> finalize
clarify -> finalize
risky_action -> approval
dead_letter -> finalize
finalize -> END
```

Conditional edges:

```text
classify -> route_after_classify
evaluate -> route_after_evaluate
retry -> route_after_retry
approval -> route_after_approval
```

Checklist:

- [ ] Import LangGraph bên trong builder nếu cần giữ import-safe behavior.
- [ ] `StateGraph(AgentState)` được dùng đúng.
- [ ] Conditional path maps chứa đủ node đích.
- [ ] `graph.compile(checkpointer=checkpointer)`.
- [ ] Không tạo direct edge bỏ qua `finalize`.
- [ ] Error route bắt đầu ở `retry`, không gọi tool trước khi tăng attempt theo contract hiện tại.
- [ ] Risky route bắt buộc qua approval.

## 7. Work package D — Tests

Các test tối thiểu:

- [ ] State có đầy đủ field mới.
- [ ] Append reducer giữ toàn bộ events qua nhiều nodes.
- [ ] Mọi route classify trả đúng node name.
- [ ] Unknown route fallback về answer.
- [ ] Retry trong giới hạn và tại giới hạn.
- [ ] Approval approved/rejected/missing.
- [ ] Graph đăng ký đúng 11 nodes.
- [ ] Mọi terminal path có `finalize`.
- [ ] Không có retry path không giới hạn.

Lệnh chạy riêng:

```bash
pytest tests/test_state.py tests/test_routing.py tests/test_graph_structure.py -q
```

## 8. Commit plan

1. `feat(state): define serializable agent state contract`
2. `feat(routing): implement bounded conditional routes`
3. `feat(graph): wire complete terminating workflow`
4. `test(graph): cover state routing and topology`
5. `docs(graph): export mermaid architecture evidence`

Push commit state contract sớm nhất để Người 2 và Người 4 có thể rebase.

## 9. Definition of done

- Không còn `TODO(student)` trong ba file ownership chính.
- Routing tests pass hoàn toàn.
- Graph compile với `None`, MemorySaver và checkpointer do Người 3 cung cấp.
- Mermaid diagram khớp code thực tế.
- Không chỉnh file của thành viên khác.
- Handoff cho Người 3 gồm commit hash, commands đã chạy và giới hạn còn biết.

