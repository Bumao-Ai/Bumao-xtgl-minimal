# Bumao XTGL Minimal 零基础 GitHub 上传教程（照着做就能跑通）

> 本教程面向**从没用过 git / GitHub** 的人。每条命令都给"复制原文"和"看到什么算成功"。
> 全程在 Windows + PowerShell 下操作。你的 GitHub 用户名下面一律用 `<your-user>` 表示，
> 仓库名用 `bumao-xtgl-minimal`，请把它们换成你自己的。
>
> 本教程对应的项目就是本仓库（Bumao XTGL Minimal），本地项目根目录是 `10_rac\`。

---

## T1 · 注册 GitHub 账号并完成邮箱验证

1. 打开 <https://github.com/signup>。
2. 输入一个你**能收信**的邮箱（建议用常用邮箱，后面加 SSH 公钥、收通知都靠它）。
3. 设密码、起用户名（用户名会出现在仓库网址里，以后改起来麻烦，想好再起）。
4. 收到验证邮件后，点邮件里的链接完成验证。
5. 登录后右上角头像能看到，就算账号 OK。

**看到什么算成功**：能登录 <https://github.com>，右上角是你的头像，不是"Sign in"。

> 截图位（登记用，实际操作时自己补）：
> 【截图1-1：注册页】  【截图1-2：邮箱已验证提示】

---

## T2 · 安装 Git for Windows

1. 下载：<https://git-scm.com/download/win> （会自动给 64 位安装包，要求版本 ≥ 2.40）。
2. 双击安装，**一路下一步时注意这三个勾选项的取舍**：
   - **"Adjusting your PATH environment"（调整 PATH）**：选第二项
     **"Git from the command line and also from 3rd-party software"**（默认就是它，别动）。
     这一项决定你能不能在 PowerShell 里直接敲 `git`。
   - **"Choosing the SSH executable"**：选 **"Use bundled OpenSSH"**（默认，用自带 SSH）。
   - **"Choosing the default editor used by Git"**：选你顺手的编辑器，
     新手选 **Vim** 或 **Nano** 都行（不影响命令行操作）。
3. 装完**关掉再重新打开 PowerShell**（让 PATH 生效），验证：

```powershell
git --version
```

**看到什么算成功**：输出一行 `git version 2.xx.x.windows.x`，而不是"无法识别 git"。

---

## T3 · 配置你的身份（提交记录里显示的名字和邮箱）

```powershell
git config --global user.name  "你的名字或昵称"
git config --global user.email "你注册 GitHub 用的那个邮箱"
```

验证：

```powershell
git config --global user.name
git config --global user.email
```

**看到什么算成功**：上面两条命令分别回显你刚填的名字和邮箱。

> 说明：`--global` 是对这台机器上所有仓库生效。如果你只想给本项目单独配，
> 就去掉 `--global` 并在项目目录里执行（效果一样，二选一）。

---

## T4 · 生成 SSH 密钥，并把公钥加到 GitHub

用 SSH 推送不用每次输密码。把下面邮箱换成你自己的：

```powershell
ssh-keygen -t ed25519 -C "you@example.com"
```

执行后会问三个问题，**全部直接按回车**（不设密码短语，省得每次输）：

```
Enter file in which to save the key (...):        <- 直接回车
Enter passphrase (empty for no passphrase):      <- 直接回车
Enter same passphrase again:                     <- 直接回车
```

然后**复制公钥内容**（注意是 `.pub` 那个公钥，不是私钥）：

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

输出是一行，以 `ssh-ed25519 AAAA....` 开头、以你的邮箱结尾。**整行复制**。

加到 GitHub：
1. 打开 <https://github.com/settings/keys> （头像 → Settings → SSH and GPG keys）。
2. 点 **New SSH key**。
3. Title 随便起（比如"我的 Windows 笔记本"）。
4. Key 框里粘贴刚才整行公钥。
5. 点 **Add SSH key**。

**看到什么算成功**：列表里出现你刚加的那把 key。

> 私钥 `id_ed25519`（没有 `.pub` 的那个）永远不要发给任何人、不要上传。

---

## T5 · 验证 SSH 能连上 GitHub

```powershell
ssh -T git@github.com
```

第一次会问 `Are you sure you want to continue connecting (yes/no)?`，敲 `yes` 回车。

**看到什么算成功**：输出
`Hi <your-user>! You've successfully authenticated, but GitHub does not provide shell access.`
（看到 `successfully authenticated` 就成了，"does not provide shell access" 是正常的，不是报错。）

---

## T6 · 在 GitHub 网页端新建空仓库

1. 打开 <https://github.com/new>。
2. **Repository name** 填 `bumao-xtgl-minimal`。
3. Description 可填：`A rules-as-code governance layer for AI agents.`
4. 选 **Public**（开源要公开；想先藏着就选 Private）。
5. **不要勾** "Add a README"、**不要勾** "Add .gitignore"、**不要选** "Choose a license"。
   - 原因：本项目已经自带这三个文件。如果让 GitHub 再生成一份，
     你本地推送时会和网页版各有一份初始文件，直接冲突、推不上去。
6. 点 **Create repository**。
7. 建完页面会显示一个地址 `git@github.com:<your-user>/bumao-xtgl-minimal.git`，**复制它**，下一步要用。

**看到什么算成功**：跳转到一个空仓库页面，提示"Quick setup"，上面有那条 SSH 地址。

---

## T7 · 本地初始化并首次推送（全流程照抄）

> 下面在项目根目录里执行（也就是本仓库解压/clone 后最外层那一层，里面有 BumaoXTGL_Minimal_v01.py）。
> 发布包随附 `kernel/bumao_core`；解压或克隆时须连同内核目录一起带上，放在本仓库外层同级的位置，否则 `check --strict` 会打印 `[FATAL] missing gate kernel` 并以 exit=2 退出（详见 `10_rac/README.md` 的 *Kernel placement*）。
> 先用资源管理器进到那一层，再在地址栏敲 `powershell` 回车打开终端，或手动 cd 过去：
>
> ```powershell
> cd path\to\bumao-xtgl-minimal     # 换成你本机项目根目录的真实路径
> ```

```powershell
# 1) 初始化 git 仓库，默认分支命名为 main
git init -b main

# 2) 把所有文件加入暂存区
git add .

# 3) 看一眼暂存区（教你怎么读）
git status
```

`git status` 怎么看：
- 绿色的 `new file:` 是即将提交的文件；
- 如果你看到红色 `untracked files`，说明上一步 `git add .` 没执行成功；
- `gitignore` 里写过的 `logs/`、`tests/_tmp_*`、`__pycache__/`、`selfcheck.py` **不会**出现在列表里，这是对的。

```powershell
# 4) 提交第一个版本（引号里是说明文字，可改）
git commit -m "Initial release: Bumao XTGL Minimal 0.10"

# 5) 把本地仓库关联到你在 T6 建的空仓库（地址换成你自己的）
git remote add origin git@github.com:<your-user>/bumao-xtgl-minimal.git

# 6) 首次推送，并把本地 main 关联到远端 origin/main
git push -u origin main
```

**看到什么算成功**：最后一条命令输出类似
`Enumerating objects: ... Writing objects: 100% ... To github.com:<your-user>/bumao-xtgl-minimal.git * [new branch] main -> main`。
刷新 GitHub 仓库网页，能看到所有文件。

验证命令（不推送也能自查）：

```powershell
git log --oneline      # 应看到 1 条提交 "Initial release: Bumao XTGL Minimal 0.10"
git status             # 应显示 "nothing to commit, working tree clean"
git remote -v          # 应列出 origin = git@github.com:<your-user>/bumao-xtgl-minimal.git
```

---

## T8 · 常见报错与修复（每条都给错误原文 + 修法）

### 报错 1：`Permission denied (publickey)`

推送时看到：
```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
```
**原因**：SSH 公钥没加对，或本机私钥没被找到。
**修法**：
```powershell
# a. 先测连通，确认是不是 SSH 问题
ssh -T git@github.com
# b. 如果这里也报 Permission denied，回到 T4 重新加公钥；
#    确认你复制的是 .pub 公钥整行，且 GitHub 上那把 key 没删。
# c. 确认远端用的是 SSH 地址而不是 HTTPS 地址：
git remote -v
#    如果显示 https://github.com/...，改成 SSH：
git remote set-url origin git@github.com:<your-user>/bumao-xtgl-minimal.git
```

### 报错 2：`src refspec main does not match any`

推送时看到：
```
error: src refspec main does not match any
error: failed to push some refs to 'git@github.com:...'
```
**原因**：你还没有任何提交，本地根本没有 `main` 分支。
**修法**：按顺序补齐 `add` 和 `commit`，再推：
```powershell
git add .
git commit -m "Initial release: Bumao XTGL Minimal 0.10"
git log --oneline     # 这一步必须能看到提交记录，再 push
git push -u origin main
```

### 报错 3：`failed to push some refs ... fetch first` / 非快进

推送时看到：
```
 ! [rejected]        main -> main (non-fast-forward)
error: failed to push some refs to 'git@github.com:...'
hint: Updates were rejected because the remote contains work that you do not have locally.
```
**原因**：远端已经有提交（比如你在网页端勾了 README，或别人推过），本地和远端分叉了。
**修法**：先把远端拉下来、变基到本地提交之上，再推：
```powershell
git pull --rebase origin main
# 如果有冲突，按提示改完：
#   git add <冲突文件>
#   git rebase --continue
# 然后再推：
git push -u origin main
```

### 报错 4：文件超过 100 MB，被 GitHub 拒收

推送时看到：
```
remote: error: File xxx is 150.00 MB; this exceeds GitHub's file size limit of 100.00 MB
```
**原因**：仓库里混进了大文件（本项目是纯文本，正常不会遇到；若你加了产物/数据集才会）。
**修法**（二选一）：
- 把大文件加进 `.gitignore`，并从历史里清掉（简单做法：删掉那个文件再提交）：
```powershell
# 假设大文件是 build/big.bin
Add-Content .gitignore "build/big.bin"
git rm --cached build/big.bin
git commit -m "Stop tracking large build artifact"
```
- 或用 Git LFS 管理大文件：
```powershell
git lfs install
git lfs track "*.bin"
git add .gitattributes
git add build/big.bin
git commit -m "Track large files via Git LFS"
```

### 报错 5：中文文件名在 git 里显示成 `\345\244\247\345\220\210` 八进制乱码

`git status` 里中文文件名显示成一串 `\xxx\xxx`。
**原因**：git 默认把非 ASCII 文件名转义。
**修法**：
```powershell
git config --global core.quotepath false
git status      # 再看，中文文件名就正常显示了
```

---

## T9 · 发布一个 Release（打版本标签）

代码推上去之后，发一个正式版本：

```powershell
cd path\to\bumao-xtgl-minimal     # 你的项目根目录

# 1) 打一个带备注的标签（版本号和 meta.json 里的一致）
git tag -a v0.10 -m "Bumao XTGL Minimal 0.10: first public release"

# 2) 把标签推到远端
git push origin v0.10
```

然后在网页端写 Release Notes：
1. 打开仓库页面 → 右侧 **Releases** → **Draft a new release**。
2. **Choose a tag** 选你刚推的 `v0.10`。
3. Release title 填 `v0.10`。
4. Describe 里写这个版本干了什么（抄 README 的亮点即可）。
5. 如果有产物（zip、wheel），在 **Attach binaries** 里拖进去。
6. 点 **Publish release**。

**看到什么算成功**：仓库 Releases 页面出现 `v0.10`，可下载。

---

## T10 · 后续维护：把"真身"的新版本单向同步到开源版

> 这是本项目最重要的纪律：**改前先备份，改后必须渲染并过闸，绝不手改视图。**

以后真身升级了，按这个流程把改动"翻译"进开源版：

```powershell
# 1) 在开源项目目录里，先确认本地是干净的
cd path\to\bumao-xtgl-minimal
git status                 # 必须 working tree clean

# 2) 从真身拷过来的改动，逐个人工甄别：
#    - 只拷"通用、无私有信息"的部分；
#    - 私有业务词、个人信息、绝对路径一律不带（见下）；
#    - 改完立刻跑脱敏四查（见下节「同步红线」）。

# 3) 重渲染 + 跑闸门 + 跑测试，必须全绿
python render.py write
python BumaoXTGL_Minimal_v01.py check --strict          # 必须 ALL PASS (27 gates)
python -m unittest discover tests        # 必须 OK

# 4) 升版本号（只改 meta.json 一处），再提交推送
python BumaoXTGL_Minimal_v01.py bump
git add .
git commit -m "Sync: bring generic improvements from internal core"
git push
```

**同步红线（每次都要过一遍）**：
- 不带 `sk-` 开头的密钥（20 位以上）；
- 不带个人姓名、机器名、盘符绝对路径；
- 不带任何私有业务代号、内部产品名或项目名（一律换成通用词或删掉）；
- 闸门不全绿、测试不过，不提交、不推送。

---

## 附：本项目"可一键推送"状态说明

本仓库已在本地准备到"差最后一步"的状态：
- 代码、README、LICENSE(Apache-2.0)、CONTRIBUTING、tests、CI 都齐；
- 本地 git 已初始化、已提交、**未加任何远端、未 push**（真实推送属对外发布动作，
  需负责人批准后，由本人按 T6/T7 执行）；
- 推送前的演练用的是**本地裸仓库 dry-run**，没有碰真实 GitHub。
