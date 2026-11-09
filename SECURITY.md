# 安全政策 / Security Policy

## 报告安全问题

请**不要**在公开 Issue 中披露漏洞细节。请使用 GitHub 仓库的私密报告渠道：

- 打开仓库页面 → **Security** → **Advisories** → **Report a vulnerability**

维护者会在私密通道中与你确认复现步骤、影响范围与修复方案。

## 在范围内的问题

- 闸门可被绕过、伪造或静默跳过（例如篡改判定结果、伪造 ALL PASS）。
- 防缩水机制失效（注释掉 `register()` 或改动 `set_expected()` 后仍能通过）。
- 规则装载、索引、审计中的路径穿越或任意文件读写。
- 控制台接口的未授权访问、命令注入、目录遍历。
- 仓库中意外包含真实路径、用户名、主机名、凭据或个人信息。

## 不在范围内的问题

- 用户自己写入的规则内容是否正确、是否合理。
- 用户自行改造后引入的问题（请先确认原始版本可复现）。
- 社会工程、物理访问、第三方服务自身的漏洞。

## 处理约定

- 我们会尽快确认收到报告，并在修复发布后致谢（如你愿意具名）。
- 修复前请勿公开细节；修复发布后可由你或维护者撰写公告。
- 请勿在报告中粘贴真实个人信息；必要时用 `example/` 占位。

---

# Security Policy（English）

## Reporting a security issue

Please do **not** disclose vulnerability details in a public Issue. Use the private reporting channel of the hosting repository:

- Open the repository page → **Security** → **Advisories** → **Report a vulnerability**

The maintainers will confirm reproduction steps, impact and a fix with you in the private thread.

## In scope

- A gate can be bypassed, forged or silently skipped (for example a tampered verdict or a forged ALL PASS).
- The anti-shrink mechanism fails (a run still passes after `register()` is commented out or `set_expected()` is altered).
- Path traversal or arbitrary file read/write in rule loading, indexing or auditing.
- Unauthorized access, command injection or directory traversal in the console endpoints.
- Real paths, user names, hostnames, credentials or personal data accidentally committed to the repository.

## Out of scope

- Whether rule content you wrote yourself is correct or reasonable.
- Problems introduced by your own modifications (confirm first that the original version reproduces them).
- Social engineering, physical access, or vulnerabilities in third-party services themselves.

## Handling

- We will acknowledge your report as soon as possible and credit you after the fix ships (if you wish to be named).
- Please do not publish details before the fix; after it ships, either you or the maintainers may write the advisory.
- Do not paste real personal data into a report; use `example/` placeholders where needed.
