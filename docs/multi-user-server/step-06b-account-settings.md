# Step 06B - Account Settings

## Goal
在设置弹窗里补齐“用户信息/账号”分区，让当前登录用户可以查看账号信息、编辑显示名和个人说明、修改密码、退出登录。

## What Changed
- 在 `frontend/src/components/workspace/settings/settings-dialog.tsx` 新增了 `account` section，并加入左侧设置导航。
- 新增 `frontend/src/components/workspace/settings/account-settings-page.tsx`，承载账号页内容。
- 账号页展示：
  - 用户 ID
  - 邮箱
  - 角色
  - 显示名
  - 个人说明/Profile
- 账号页支持：
  - 修改显示名
  - 更新 Profile 文本
  - 修改密码
  - 退出登录
- 前端新增认证 hooks 和 API 封装：
  - `frontend/src/core/auth/api.ts`
  - `frontend/src/core/auth/hooks.ts`
- Profile 仍走后端现有 per-user profile 链路；账号基础信息则来自前端 session。

## Interfaces
- 账号信息读取：`GET /api/auth/session`
- 修改显示名：`PATCH /api/auth/profile`
- 修改密码：`POST /api/auth/change-password`
- 登出：`POST /api/auth/logout`
- 用户 Profile：
  - `GET /api/user-profile`
  - `PUT /api/user-profile`

## Verification
- 已检查设置弹窗 section 切换、账号表单、密码表单和登出动作的前端调用链路。
- 已确认账号页的数据源分离：session 信息与 user profile 不再混成一块。

## Known Limits
- 首版不提供用户管理后台。
- 首版没有邀请成员、组织管理和角色编辑入口。
- 当前没有把用户昵称同步展示到侧边栏头像位；这可以在后续 UI 收尾时补充。
