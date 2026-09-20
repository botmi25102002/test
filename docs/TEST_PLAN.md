# Manual Test Plan: Tier 2

## 1. Scope & Objective
- **Mục tiêu kiểm thử**: Xác thực các tính năng Authentication và Authorization, cũng như luồng quản lý Todo và các edge cases (bộ đệm, cô lập dữ liệu).
- **Phạm vi kiểm thử**: Authentication (Đăng ký, Đăng nhập, Đăng xuất), Todo CRUD, Authorization (Phân quyền sở hữu), Caching (Redis Invalidation).

## 2. Test Environment & Prerequisites
- **Base URL Backend**: `http://localhost:8000`
- **Base URL Frontend**: `http://localhost:3000`
- **Pre-seeded Test Accounts**:
  - Account 1 (User A): `user_a@test.com` / `Password@123`
  - Account 2 (User B): `user_b@test.com` / `Password@123`

## 3. Test Cases Matrix

| TC ID | Module / Feature | Test Scenario | Preconditions | Test Steps | Expected Result | Priority / Severity | Status |
|---|---|---|---|---|---|---|---|
| TC-01 | Auth | Login thành công với mật khẩu đúng | User đã đăng ký | 1. Nhập email/pass đúng<br>2. Bấm Login | Trả về token, chuyển hướng vào Todo page | High / Blocker | Pass |
| TC-02 | Auth | Login thất bại với mật khẩu sai (Tránh User Enumeration) | User đã đăng ký | 1. Nhập email đúng, pass sai<br>2. Bấm Login | Báo lỗi chung "Invalid email or password" (HTTP 401) | Medium / Security | Pass |
| TC-03 | Todo Security | User A không thể sửa Todo của User B | User A & B đã login | 1. User B tạo todo ID X<br>2. User A gọi PUT /todos/X | Trả về 403 Forbidden hoặc 404 Not Found | High / Critical | Pass |
| TC-04 | Todo Logic | Đổi trạng thái todo hoàn thành sang chưa hoàn thành | Todo đang completed | 1. Bấm checkbox bỏ completed<br>2. Refresh trang | Todo vẫn ở trạng thái incomplete (completed = false) | Medium / Major | Pass |
| TC-05 | Cache | Cập nhật Todo xóa cache lập tức | Todo đã được cache | 1. Sửa title Todo<br>2. F5 hoặc gọi GET /todos | Hiển thị title mới, không nhận cache cũ | Medium / Major | Pass |
| TC-06 | Auth | Đăng xuất xóa dữ liệu bộ nhớ UI | User đã đăng nhập | 1. Bấm Logout<br>2. User khác đăng nhập vào | Không hiển thị Todo cũ (React Query cache đã bị xóa) | High / Critical | Pass |
| TC-07 | Todo Logic | Sửa Title không xóa Description | Todo có cả Title và Description | 1. Gọi PUT /todos/X cập nhật title<br>2. Kiểm tra lại todo | Description ban đầu vẫn được giữ nguyên | Medium / Minor | Pass |
| TC-08 | Auth | JWT token hết hạn | Token cũ > 30 phút | 1. Dùng token đã quá hạn gọi API | Trả về HTTP 401 Unauthorized "Token has expired" | High / Security | Pass |

## 4. Defect Tracking & Known Limitations
- Cần chạy đầy đủ E2E tests với Playwright để xác thực luồng Frontend cho các case trên.
- Cache invalidation hiện tại thực thi qua `scan_iter` nên có thể ảnh hưởng nhỏ đến hiệu năng nếu Redis lớn (sẽ cân nhắc migrate sang cấu trúc Hash thay vì key-value ở Tier 3).
