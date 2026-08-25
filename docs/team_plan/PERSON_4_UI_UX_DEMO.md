# Người 4 — Streamlit UI/UX & Demo Engineer

## 1. Mission

Xây dựng một Agent Operations Console bằng Streamlit để demo đầy đủ graph backend: chạy ticket, xem route/timeline, pause tại approval, approve/reject rồi resume, xem retry/dead-letter, metrics và checkpoint history. UI không được tái triển khai business logic của backend.

Branch: `feat/demo-ui`

## 2. File ownership

Được tạo/sửa:

```text
ui/streamlit_app.py
ui/components.py
ui/styles.css
ui/README.md
tests/test_ui_helpers.py
docs/DEMO_GUIDE.md
reports/evidence/ui/
```

Không được sửa:

```text
src/langgraph_agent_lab/state.py
src/langgraph_agent_lab/routing.py
src/langgraph_agent_lab/graph.py
src/langgraph_agent_lab/nodes.py
src/langgraph_agent_lab/llm.py
src/langgraph_agent_lab/persistence.py
src/langgraph_agent_lab/metrics.py
src/langgraph_agent_lab/cli.py
pyproject.toml
Makefile
configs/
reports/lab_report.md
```

Gửi dependency/config request cho Người 3. Gửi backend contract issue cho đúng owner, không tự sửa backend.

## 3. Product và UX direction

Tên demo: **Agent Lab Console**.

Phong cách:

- Minimal/Swiss, chuyên nghiệp, rõ trạng thái.
- Tập trung vào observability và human control.
- Không dùng hiệu ứng nặng hoặc animation làm chậm demo.

Design tokens:

```text
Primary:        #7C3AED
Background:     #FAF5FF
Card:           #FFFFFF
Foreground:     #0F172A
Muted text:     #475569
Border:         #EFE7FC
Success:        #15803D
Warning:        #B45309
Destructive:    #DC2626
Focus ring:     #7C3AED
Heading font:   Outfit
Body font:      Work Sans
```

Accessibility requirements:

- [ ] Text contrast tối thiểu 4.5:1.
- [ ] Không chỉ dùng màu để phân biệt success/error/risky.
- [ ] Button có label rõ, không dùng icon-only button thiếu aria/tooltip.
- [ ] Target tương tác tối thiểu khoảng 44px.
- [ ] Keyboard focus nhìn thấy rõ.
- [ ] Không loại bỏ native focus ring nếu chưa có thay thế.
- [ ] Loading, success và error feedback xuất hiện gần hành động.
- [ ] Không dùng emoji làm icon chính.
- [ ] Kiểm tra viewport 375, 768, 1024 và 1440px.

## 4. Kiến trúc UI đề xuất

```text
ui/streamlit_app.py
  ├─ initialize session state
  ├─ build/load graph + checkpointer
  ├─ ticket form
  ├─ invoke/resume orchestration
  ├─ tabs/layout
  └─ call reusable render helpers

ui/components.py
  ├─ render_status_badge
  ├─ render_execution_timeline
  ├─ render_approval_panel
  ├─ render_metrics_cards
  ├─ render_scenario_table
  └─ render_checkpoint_history

ui/styles.css
  └─ scoped visual tokens and accessibility states
```

Business decisions như route, retry hoặc approval result phải đi qua backend graph.

## 5. Work package A — Session và backend adapter

Streamlit rerun làm mất biến local, nên lưu tối thiểu trong `st.session_state`:

```text
graph
checkpointer
thread_id
current_state
pending_interrupt
last_error
metrics_report
```

Checklist:

- [ ] Tạo unique thread ID cho ticket mới.
- [ ] Không tái tạo checkpointer/database connection vô hạn trên mỗi rerun.
- [ ] Cùng ticket giữ đúng thread ID qua approve/reject.
- [ ] Có nút New ticket để reset session state có kiểm soát.
- [ ] Không hiển thị API key hoặc raw environment.
- [ ] Exception backend được hiển thị dạng user-friendly, chi tiết kỹ thuật nằm trong expandable debug section.

## 6. Work package B — Ticket Runner

Input controls:

- Query text area có label rõ.
- Max attempts, mặc định 3.
- Checkpointer selector: Memory/SQLite.
- Toggle demo real HITL nếu backend hỗ trợ.
- Run button.

Validation:

- Empty query không được invoke graph.
- Hiển thị inline error gần text area.
- Disable hoặc chống double submit khi đang chạy.
- Có loading indicator trong lúc gọi LLM.

Output summary:

- Route.
- Risk level.
- Thread ID dạng copyable text.
- Final answer hoặc pending question.
- Completion/error status.

## 7. Work package C — Execution Timeline

Mỗi event hiển thị:

- Node name.
- Event type/status.
- Message ngắn.
- Latency nếu có.
- Metadata trong expandable detail.

Visual semantics:

- Completed: icon + text + green.
- Pending approval: icon + text + amber.
- Error/retry: icon + text + red/amber.
- Dead letter: destructive callout.

Không dựa duy nhất vào màu. Timeline phải cho thấy rõ:

```text
intake -> classify -> retry -> tool -> evaluate -> ... -> finalize
```

## 8. Work package D — Approval Inbox và resume

Khi graph trả interrupt:

- Hiển thị original query.
- Hiển thị proposed action.
- Hiển thị risk level/lý do cần approval.
- Reviewer input.
- Comment input.
- Hai nút riêng: Approve và Reject.

Resume payload:

```python
{
    "approved": True_or_False,
    "reviewer": reviewer_name,
    "comment": reviewer_comment,
}
```

Resume bằng cùng graph config/thread ID:

```python
Command(resume=decision)
```

Checklist:

- [ ] Approve không tạo thread mới.
- [ ] Reject không thực hiện tool side effect.
- [ ] Chống double-click/double resume.
- [ ] Sau resume, timeline nối tiếp lịch sử cũ.
- [ ] Audit approval có reviewer/comment.
- [ ] UI hiển thị rõ trạng thái đã duyệt hoặc từ chối.

## 9. Work package E — Metrics và persistence views

Metrics tab:

- Success rate.
- Total scenarios.
- Average nodes visited.
- Total retries.
- Total approvals/interrupts.
- Resume success.
- Scenario result table.
- Bar chart retry hoặc latency nếu dữ liệu đủ.

Persistence tab:

- Thread ID hiện tại.
- Checkpoint count.
- Danh sách state snapshots theo thứ tự.
- Node/next state nếu API cung cấp.
- Nút refresh history.

Không tự tính metric khác với backend nếu backend đã cung cấp `MetricsReport`.

## 10. Work package F — Responsive layout

Desktop:

```text
Sidebar: controls/checkpointer
Main: ticket + answer
Right/secondary: route and risk summary
Tabs: Timeline | Approval | Metrics | History
```

Mobile/tablet:

- Chuyển về một cột.
- Approval buttons không tràn ngang.
- Tables có cách xem hợp lý, không gây page-level horizontal scroll.
- Nội dung kỹ thuật dài nằm trong expandable block.

## 11. Work package G — Tests và evidence

Helper tests không cần mở browser:

- [ ] Normalize state/event data.
- [ ] Approval payload validation.
- [ ] Missing optional fields không làm crash renderer.
- [ ] Status mapping có text label ngoài màu.
- [ ] Session reset không xóa database ngoài ý muốn.

Manual QA:

- [ ] Simple route.
- [ ] Tool route.
- [ ] Risky approve.
- [ ] Risky reject.
- [ ] Error retry recovery.
- [ ] Dead letter.
- [ ] Backend/API key error.
- [ ] Mobile viewport.

Evidence cần lưu:

```text
reports/evidence/ui/01-ticket-runner.png
reports/evidence/ui/02-approval-pending.png
reports/evidence/ui/03-approval-resumed.png
reports/evidence/ui/04-retry-timeline.png
reports/evidence/ui/05-metrics-dashboard.png
reports/evidence/ui/06-state-history.png
```

## 12. Demo guide

`docs/DEMO_GUIDE.md` phải ghi:

- Environment variables cần thiết nhưng không chứa giá trị secret.
- Install/run commands.
- Thứ tự scenario demo.
- Expected UI state tại mỗi bước.
- Fallback plan nếu LLM provider tạm lỗi: dùng evidence đã chụp, không giả rằng live call thành công.
- Thời lượng mục tiêu 5–7 phút.

## 13. Commit plan

1. `feat(ui): scaffold agent operations console`
2. `feat(ui): add ticket runner and execution timeline`
3. `feat(ui): add hitl approval and resume flow`
4. `feat(ui): add metrics and checkpoint history views`
5. `test(ui): cover state adapters and approval payloads`
6. `docs(demo): add runbook and visual evidence`

## 14. Definition of done

- `streamlit run ui/streamlit_app.py` khởi động từ clean environment.
- UI dùng graph/backend thật, không duplicate routing logic.
- Risky flow pause, approve/reject và resume đúng thread.
- Retry/dead-letter có thể quan sát rõ.
- Metrics/history hiển thị dữ liệu backend.
- Accessibility và responsive checklist đạt.
- Evidence và demo guide được bàn giao cho Người 3.

