# Người 3 — Persistence, Metrics, QA & Integration Engineer

## 1. Mission

Chịu trách nhiệm biến các module riêng lẻ thành deliverable có thể cài, chạy, chấm và demo từ clean environment. Đây là owner duy nhất của dependencies, config, CLI, persistence, metrics, report và integration branch.

Branch: `feat/observability-qa`

## 2. File ownership

Được sửa:

```text
src/langgraph_agent_lab/persistence.py
src/langgraph_agent_lab/metrics.py
src/langgraph_agent_lab/report.py
src/langgraph_agent_lab/cli.py
src/langgraph_agent_lab/scenarios.py
src/langgraph_agent_lab/__init__.py
configs/
pyproject.toml
Makefile
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
.gitignore
.env.example
README.md
reports/lab_report.md
outputs/metrics.json
tests/test_metrics.py
tests/test_graph_smoke.py
tests/test_persistence.py
tests/test_cli.py
tests/test_scenarios.py
```

Không sửa logic trong:

```text
src/langgraph_agent_lab/state.py
src/langgraph_agent_lab/routing.py
src/langgraph_agent_lab/graph.py
src/langgraph_agent_lab/nodes.py
src/langgraph_agent_lab/llm.py
ui/
```

Nếu integration test phát hiện lỗi trong file owner khác, tạo reproduction và giao owner sửa.

## 3. Vai trò integrator

- Nhận commit hash từ Người 1, Người 2, Người 4.
- Merge/cherry-pick theo đúng thứ tự dependency.
- Resolve shared/config conflict; không tự viết lại logic domain của owner khác.
- Chạy final formatting/lint sau khi merge tất cả.
- Gắn tag hoặc ghi lại final commit dùng để demo.

## 4. Work package A — Environment và dependencies

Mục tiêu chuẩn: Python 3.11 trong virtual environment sạch.

Dependencies cần xác nhận:

- Core/dev dependencies hiện tại.
- `python-dotenv`.
- Một LLM provider chính, ưu tiên provider có key hợp lệ.
- `langgraph-checkpoint-sqlite`.
- `streamlit` cho UI.
- Type stubs cần thiết như `types-PyYAML` nếu mypy yêu cầu.

Checklist:

- [ ] `make install` cài đủ phần cần cho test cơ bản.
- [ ] Có command rõ ràng để cài provider/UI extras.
- [ ] CI không phụ thuộc secret để chạy unit tests.
- [ ] Integration tests cần API key được mark/skip rõ.
- [ ] Loại bỏ xung đột pytest plugin bằng venv sạch, không dùng workaround làm giải pháp chính.
- [ ] `.env.example` chỉ chứa placeholder an toàn.
- [ ] Dockerfile cài đúng extras hoặc ghi rõ cách inject provider/API key.

## 5. Work package B — Persistence

Implement `build_checkpointer()`:

- `none` -> `None`.
- `memory` -> `MemorySaver`.
- `sqlite` -> `SqliteSaver` với `sqlite3.connect()`.
- Bật WAL nếu phù hợp.
- Dùng `check_same_thread=False` nếu Streamlit cần truy cập qua reruns/threads.
- Database path lấy từ config/database URL rõ ràng.
- Unknown kind -> `ValueError`.
- Postgres là optional; không làm chậm core deliverable.

Tests:

- [ ] MemorySaver build thành công.
- [ ] SQLite file được tạo ở temporary directory.
- [ ] Cùng `thread_id` đọc được state/history.
- [ ] Hai thread không trộn state.
- [ ] Checkpoint đọc được sau khi đóng/mở lại process hoặc connection.
- [ ] Không test bằng cách ghi database vào repo.

Evidence cần tạo:

- Log hoặc screenshot state history.
- Mô tả thread ID và checkpoint count.
- `resume_success=True` chỉ khi evidence/test thực sự đạt.

## 6. Work package C — Metrics và latency

Đảm bảo `MetricsReport` đúng specification:

- `total_scenarios`.
- `success_rate`.
- `avg_nodes_visited`.
- `total_retries`.
- `total_interrupts`.
- `resume_success`.
- Per-scenario metrics.

Checklist:

- [ ] Đo wall-clock latency quanh mỗi `graph.invoke()`.
- [ ] Gán `latency_ms` vào `ScenarioMetric`.
- [ ] Đếm retry dựa trên normalized events.
- [ ] Đếm approval/interrupt dựa trên approval event.
- [ ] Approval required phải có approval observed.
- [ ] Success cần route đúng và có answer/question.
- [ ] Errors được serialize thành list string.
- [ ] Không hard-code metrics cho bảy sample IDs.
- [ ] `write_metrics()` tạo thư mục output an toàn.

## 7. Work package D — CLI và scenario runner

Checklist:

- [ ] Load YAML config an toàn.
- [ ] Load `.env` trước khi build LLM/graph hoặc đảm bảo `llm.py` đã làm.
- [ ] Mỗi scenario có `thread_id` riêng.
- [ ] Checkpointer chỉ build một lần và dùng đúng lifecycle.
- [ ] Chạy đủ scenario dù một scenario lỗi: cân nhắc ghi metric failure thay vì làm mất toàn report.
- [ ] Có error message rõ nếu thiếu provider hoặc config.
- [ ] Report được sinh sau metrics.
- [ ] `validate-metrics` kiểm tra schema và minimum scenario count.

## 8. Work package E — Report

`render_report()` phải sinh Markdown gồm:

1. Team/student metadata placeholders hoặc dữ liệu cấu hình.
2. Architecture và Mermaid diagram/reference.
3. State fields và reducers.
4. Metrics summary.
5. Per-scenario table.
6. Failure analysis tối thiểu hai trường hợp.
7. Persistence/recovery evidence.
8. Extension work.
9. Improvement plan.

Nhận evidence:

- Mermaid từ Người 1.
- LLM/provider/prompt strategy từ Người 2.
- UI screenshots và demo guide từ Người 4.

Không tự nhận extension chưa được test.

## 9. Work package F — Hidden-style QA

Thêm test/scenario ngoài sample, không sửa expected behavior của sample:

- [ ] `Cancel subscription and email me` -> risky.
- [ ] `Track my order` -> tool.
- [ ] `It does not work` -> missing_info.
- [ ] `Service unavailable after deploy` -> error.
- [ ] Composite `lookup then refund` -> risky theo priority.
- [ ] Approval rejected -> clarify.
- [ ] `max_attempts=1` -> dead letter.
- [ ] Unknown route -> safe answer fallback.
- [ ] Empty/malformed tool result -> retry.
- [ ] LLM/provider exception tạo failure có thể quan sát.

## 10. Merge và release plan

Merge order:

1. Người 1: state/routing/graph.
2. Người 2: llm/nodes.
3. Code persistence/metrics/CLI của Người 3.
4. Người 4 rebase rồi merge UI.
5. Người 3 chạy final lint/typecheck/format và tạo report/metrics.

Quality gates:

```bash
make test
make lint
make typecheck
make run-scenarios
make grade-local
streamlit run ui/streamlit_app.py
```

Chạy thêm từ clean environment hoặc Docker nếu thời gian cho phép.

## 11. Commit plan

1. `build: add llm sqlite ui and typing dependencies`
2. `feat(persistence): add sqlite checkpoint and recovery support`
3. `feat(metrics): capture scenario latency retries and approvals`
4. `feat(cli): harden scenario execution and validation`
5. `feat(report): render complete grading report`
6. `test(integration): cover persistence metrics and hidden-style cases`
7. `ci: enforce test lint and typecheck gates`
8. `docs: finalize readme report and demo instructions`

## 12. Definition of done

- Clean install thành công trên Python 3.11.
- Tất cả quality gates pass.
- Sample success rate đạt 100% hoặc mọi sai lệch có blocker được chứng minh trước deadline.
- SQLite history/resume được test thật.
- Metrics và report được generate từ run thật.
- Không có secret/generated database trong git.
- Final handoff ghi commit hash, model/provider, commands và demo entrypoint.

