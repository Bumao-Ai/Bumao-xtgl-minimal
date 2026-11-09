# COMPLIANCE 自检表

| 项目 | 状态 | 说明 |
|---|---|---|
| 许可证 (Apache-2.0) | ✅ | `10_rac/LICENSE` 完整 Apache-2.0 文本，根 `NOTICE` 与 `TRADEMARK.md` 齐全 |
| SPDX 头 | ✅ | 所有 `.py` 文件头部均有 `# SPDX-License-Identifier: Apache-2.0` |
| 无遥测声明 | ✅ | `10_rac/README.md` Privacy & No telemetry 段落 |
| 无泄漏扫描 | ✅ | `yanmin_scan.py` 导出包扫描 0 命中（内部编号/路径/密钥/IP） |
| CI 门禁 | ✅ | `.github/workflows/ci.yml`：push/PR 触发，跑 check --strict + 单元测试 |
| CHANGELOG | ✅ | `CHANGELOG.md` 符合 Keep a Changelog 格式（Added/Changed/Fixed/Removed） |
| 安全披露 (SECURITY.md) | ⚠️ 待补 | 发布后补充安全漏洞披露通道 |
| SBOM (CycloneDX) | ⚠️ 待补 | 发布后用 cyclonedx-py 生成软件物料清单 |
| 双语 README | ⚠️ 待补 | 当前仅英文，后续补中文 |
| Issue/PR 模板 | ⚠️ 待补 | 发布后补 `.github/ISSUE_TEMPLATE/` |
| 30 秒演示动图 | ⚠️ 待补 | demo 脚本已有，GIF 录屏需人工录制 |

生成日期：2026-11-01

---

## English

# COMPLIANCE Self-check Table

| Item | Status | Notes |
|---|---|---|
| License (Apache-2.0) | ✅ | `10_rac/LICENSE` complete Apache-2.0 text; root `NOTICE` and `TRADEMARK.md` present |
| SPDX header | ✅ | all `.py` files carry `# SPDX-License-Identifier: Apache-2.0` in the header |
| No-telemetry statement | ✅ | `10_rac/README.md` Privacy & No telemetry section |
| Leak scan | ✅ | `yanmin_scan.py` export-package scan 0 hits (internal ids/paths/secrets/IPs) |
| CI gate | ✅ | `.github/workflows/ci.yml`: triggered on push/PR, runs check --strict + unit tests |
| CHANGELOG | ✅ | `CHANGELOG.md` follows the Keep a Changelog format (Added/Changed/Fixed/Removed) |
| Security disclosure (SECURITY.md) | ⚠️ to be added | add a security-vulnerability disclosure channel after release |
| SBOM (CycloneDX) | ⚠️ to be added | generate the software bill of materials with cyclonedx-py after release |
| Bilingual README | ⚠️ to be added | currently English only; Chinese to be added later |
| Issue/PR templates | ⚠️ to be added | add `.github/ISSUE_TEMPLATE/` after release |
| 30-second demo GIF | ⚠️ to be added | a demo script exists; the GIF screen recording needs manual recording |

Generation date: 2026-11-01
