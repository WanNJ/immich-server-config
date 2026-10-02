# Immich 服务器重建 — 交接说明

生成日期：2026-09-28　｜　最后更新：2026-09-29
机器：jackwan-X570-AORUS-ELITE

> **2026-09-29 更新摘要**：方案从「NTFS 原盘 + External Library」改为「WD 盘格式化为 ext4 + 用 immich-go 从备份盘导入到内部库」。
> 原因：备份盘已就绪（空间问题不复存在），ext4 读照片比 ntfs-3g 快 3–4 倍。目标版本 v3.2.4（原文写的 v3.2.0 已过时）。
> 旧方案保留在第 9 节作为历史记录。
>
> **进度（2026-09-29 18:00）**：第二份备份已核对（146,875 个文件、1,494.3 GB，与第一份逐文件一致，抽样 300 个 SHA-256 一致）；FYQ-LU 已改名为 `immich-backup2`。sda 已用 `format-wd-ext4.sh` 格式化为 ext4（`/dev/sda1`，UUID `d00db64d-8f0b-436b-80ff-c2b98dfe208a`，fstab 已更新，旧 fstab 备份在 `/etc/fstab.bak-ntfs-20260929`）。旧 v1.131.3 数据库备份按决定未保留。正式实例 v3.2.4 已启动，待注册管理员后导入。

---

## 1. 背景：发生了什么

2026 年 8 月中旬系统崩溃后无法启动，进入 GRUB 命令行。

**根因**：装 Ubuntu 的那块 SSD（Sabrent Rocket NVMe 4.0 1TB，插在 M2B 槽）从固件层彻底消失 —— BIOS 的 System Info 里 M2B 显示 `N/A`。换槽到 M2A 测试仍无法识别，确认是 SSD 主控失效，非插槽或主板问题。

**已处理**：走 Sabrent RMA（5 年质保，2023-01-16 从 Amazon 购入，覆盖至 2028-01），已寄回，换新型号 SB-RKTG-1TB。

**次要根因**：旧装机时 Ubuntu 和 Windows 的 EFI 引导挤在同一块盘上，所以 Linux 盘掉了之后 GRUB 仍被拉起却找不到 `/boot`。本次重装已修正 —— Ubuntu 用自己独立的 EFI 分区。

**数据库丢失原因**：旧 `docker-compose.yml` 里数据库的 bind mount 那行是注释掉的，实际用的是 Docker 命名卷 `pgdata`（在 `/var/lib/docker/volumes/`，即坏掉的系统盘上）。v3 的官方 compose 默认就是 bind mount 到 `DB_DATA_LOCATION`，本次已确认。

---

## 2. 当前硬件与磁盘布局（2026-09-29）

| 设备 | 型号 / 序列号 | 容量 | 格式 / 卷标 | 挂载点 | 内容 |
|---|---|---|---|---|---|
| `nvme1n1` | Sabrent Rocket 4 Plus | 1 TB | ext4 | `/` | Ubuntu 24.04.3；Immich 数据库、配置；`~/backups`、两个 `*-tm-rescue` |
| `nvme0n1` | SPCC | 1 TB | NTFS | 不挂载 | Windows |
| `sda` | WD40EZAZ，WD-WX72D22ESR5C（内置 SATA） | 3.7 TB | **ext4**（GPT，`sda1`），`immich-disk` | `/mnt/data` | Immich 照片库，`UPLOAD_LOCATION=/mnt/data/immich` |
| `sdb` | Seagate BUP Slim WH，NA7Z04Q5（USB） | 1.8 TB | ext4，`immich-backup` | `/media/jackwan/immich-backup` | 照片库完整副本 1（已核对） |
| `sdd` | Seagate BUP Slim RD，NA7WAZGF（USB） | 1.8 TB | ext4，`immich-backup2` | `/media/jackwan/immich-backup2` | 照片库副本 2（已核对），之后放异地 |
| `sdc` | WD My Passport，WD-WX51A555A4EU（USB） | 1 TB | ext4，`OldPersonalFiles` | `/media/jackwan/OldPersonalFiles` | `~/yaqi-tm-rescue`、`~/jack-tm-rescue`、`~/backups`（→ `old-backups/`）的备份 |

移动硬盘**不写入 fstab**（用户要求），插上后由桌面自动挂载。

### sda 说明

- 整盘 NTFS，**没有分区表**（Windows 磁盘管理显示 unallocated 属正常）。因此无法「缩小 NTFS + 新建 ext4 分区」，只能整盘格式化。
- `/etc/fstab`：`UUID="29BC88E540B8CC84"  /mnt/data  ntfs-3g  defaults,uid=1000,gid=1000,umask=022,nofail  0  0` —— 格式化后要改成新 UUID + ext4。
- SMART 健康（通电 18103 小时，重映射/待处理扇区均为 0）。
- `.env` 里旧的 `UPLOAD_LOCATION=/media/jackwan/disk_a/library` 是过时路径，已在新 `.env` 中替换。

### 读取速度实测（2026-09-29，同一批文件，清缓存后）

| 驱动 / 盘 | 3 GB 大视频 | 1,522 张照片（3.1 GB） |
|---|---|---|
| sda + ntfs-3g（当前） | 92 MB/s | 29 MB/s |
| sda + 内核 ntfs3（只读测试） | 124 MB/s | 57 MB/s |
| sdb（USB 2.5 寸）+ ext4 | 93 MB/s | 63 MB/s |
| sda + ext4（估算） | ~150–180 MB/s | ~90–130 MB/s |

---

## 3. 数据现状（2026-09-29）

### 照片库 `/mnt/data/library/library/admin/`

- **146,875 个文件，1,494.3 GB**，与 `immich-backup` 逐个核对一致。
- 其中 21,532 个（69 GB）是 2026-09-29 从旧 Mac 的 Time Machine 和旧照片图库里救出、按 `年/年-月-日/` 补进来的（Immich 原来没有的照片）。明细：`~/immich-dedupe-report/immich_import_A.csv`（含原相册名，可用于重建相册）。
- 2026-09-29 清理：删除 58 个重复副本（保留较早的一份）；`upload/` 里 162 个上传中断的残缺文件已删除，5 个完整文件移入 `library/`。操作记录在 `~/immich-dedupe-report/`。
- 最新照片拍摄日期：2026-05-31（崩溃前两个半月的空档，`upload/` 里没有发现遗漏的完整照片）。

### sda 上可再生 / 过时的内容（格式化时一并清除）

| 目录 | 大小 | 说明 |
|---|---|---|
| `encoded-video/` | 539 GB | 转码缓存，有 I/O 错误（NTFS 脏位） |
| `thumbs/` | — | 缩略图缓存 |
| `backups/` | 8.2 GB | 旧 v1.131.3 数据库 pg_dump。**决定不恢复**（见第 4 节），格式化前如需留底，复制到 SSD |
| `profile/`、`upload/` | ~0 | 已清空 |

### 其他个人数据（不进 Immich）

- `~/backups/chat-medias/{WeChat,QQ,iMessage}/年/月/`：24,495 个聊天图片/视频（7 GB）。
- `~/backups/disk-files/`：旧移动硬盘上的课程视频、文档等（97 GB）。
- `~/yaqi-tm-rescue`、`~/jack-tm-rescue`：两台旧 Mac 的 Time Machine 救出的个人文件。
- 以上都已备份到 `OldPersonalFiles` 盘。

---

## 4. 决策：全新安装 v3.2.4 + ext4 + immich-go 导入

### 为什么不恢复旧数据库（不变）

备份来自 v1.131.3（pgvecto.rs + pg14），v3 已移除 pgvecto.rs，需多段升级且易出错。**决定放弃旧索引**（相册、人物名、收藏），重跑人脸识别（RTX 3060 Ti 加速）。

### 为什么现在改用 ext4 + 内部库（替代原来的 External Library 方案）

- 原方案选 External Library 的主要理由是「空间不够同时放两份」。现在照片库在两块 USB 备份盘上各有一份，可以把 sda 整盘格式化后从备份盘导入，空间问题不存在了。
- ext4 读小文件比 ntfs-3g 快 3–4 倍，Immich 生成缩略图、ML、备份都受益。
- 内部库由 Immich 管理文件（可在 Immich 里删除、存储模板生效），External Library 做不到。

### 导入方式

`immich-go upload from-folder`，直接从备份盘读取上传（不需要先复制到 sda）。可以两块备份盘并行导入（按年份拆分），读取速度翻倍。

---

## 5. 已确认的系统状态（2026-09-29）

- GPU：NVIDIA GeForce RTX 3060 Ti（8 GB），驱动 595.91.07，`nvidia-smi` 正常。
- Docker 29.8.1，Docker Compose v5.5.1，当前用户在 `docker` 组。
- NVIDIA Container Toolkit 已装好，Docker runtimes 里有 `nvidia`。
- 镜像已拉取：`immich-server:v3.2.4`、`immich-machine-learning:v3.2.4-cuda`、`immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`、`valkey:9`。
- `tools/immich-go`：v0.32.0（sha256 已验证；`tools/` 不进 git）。

---

## 6. 本仓库的配置（v3.2.4）

- `docker-compose.yml`：官方 v3.2.4 版本，改动两处：
  - `immich-server` 启用 `hwaccel.transcoding.yml` 的 `nvenc`（NVENC 转码 + 硬件解码）。
  - `immich-machine-learning` 用 `-cuda` 镜像并启用 `hwaccel.ml.yml` 的 `cuda`。
  - 容器内照片目录在 v3 是 **`/data`**（旧版是 `/usr/src/app/upload`）。
- `.env`（**不再进 git**，含数据库密码）：`UPLOAD_LOCATION=/mnt/data/immich`，`DB_DATA_LOCATION=/home/jackwan/workspace/immich-server-config/postgres`（SSD，绝对路径），`TZ=America/Los_Angeles`，`IMMICH_VERSION=v3.2.4`（固定版本，升级前先看 release notes）。
- `.env.example`：去掉密码的模板，进 git。
- `.gitignore`：`postgres/`、`.env`、`tools/`。
- 本仓库有 GitHub 远程（`WanNJ/immich-server-config`）；**旧提交里的 `.env` 含旧数据库密码**，新密码已更换。

### 首次启动后要在 Immich 里设置的（导入前）

所有设置都在 `immich-settings.json` 里，用脚本一次应用（只改文件里列出的项，其他保持 Immich 默认）：

```bash
IMMICH_API_KEY=<管理员 API Key> ./apply-settings.py
```

硬件：Ryzen 7 5800X（8 核 16 线程）、32 GB 内存、RTX 3060 Ti 8 GB。

| 设置 | 默认 | 我们的值 | 原因 |
|---|---|---|---|
| 存储模板 | 关闭 | `{{y}}/{{y}}-{{MM}}-{{dd}}/{{filename}}` | 与旧库目录结构一致 |
| 缩略图并发 | 3 | 2 | 原设 8；sda 是 SMR 盘，高并发随机读会卡死（见下） |
| 元数据提取并发 | 5 | 2 | 同上，原设 8 |
| 附属文件（sidecar）并发 | 5 | 2 | 同上 |
| 视频转码并发 | 1 | 2 | NVENC 编码（3 路时和 ML 抢显存） |
| 人脸检测 / 智能搜索 / OCR 并发 | 2 / 2 / 1 | 2 / 2 / 1 | 跑在 GPU 上；调高会显存不足 |
| 智能搜索模型 | `ViT-B-32__openai`（仅英文） | `nllb-clip-large-siglip__v1`（多语言，支持中文） | GPU 跑得动大模型 |
| 视频转码 | 关闭硬件加速、`ultrafast` | `nvenc` + 硬件解码、`medium` | 显卡编码快，换更好的画质 |

**⚠️ 导入时遇到的坑（2026-09-29 正式实例）**

1. **任务队列被暂停**：`immich-go` 默认 `--pause-immich-jobs=true`，上传期间会暂停 Immich 的后台队列，照片没有缩略图，网页显示「Error loading image」。（最初误以为是更换 CLIP 模型导致的，已更正。）要边导入边处理，加 `--pause-immich-jobs=false`；如果队列被暂停，在「管理 → 任务」里点「继续」，或 `PUT /api/jobs/<队列名> {"command":"resume"}`。
2. **GPU 显存不足**：最初并发设为智能搜索 4、人脸 4、OCR 2、转码 3，多语言 CLIP 模型本身约占 4 GB，8 GB 显存被耗尽（ONNX Runtime「Failed to allocate memory」），部分人脸/OCR 任务失败，部分视频 NVENC 失败后退回 CPU。已降为 2 / 2 / 1 / 2（见 `immich-settings.json`）。导入后要对人脸识别、OCR 运行「处理缺失项」补跑。
3. **immich-go 遇错即停**：默认 `--on-errors=stop`，服务器高负载时一次上传连接断开（`EOF`）就终止整个导入。改用 `--on-errors=continue`；重新运行会自动跳过已上传的文件。

测试（1,606 个文件）：换模型后重建智能搜索索引用了 7.5 分钟（含首次下载模型），GPU 峰值 100%，显存峰值 3.9 GB / 8 GB；中文搜索响应约 40 ms。

### 测试结果（2026-09-29，SSD 临时实例，220 个文件）

- immich-go 上传 220/220，0 错误；照片、RAW（DNG）、视频、实况照片都正常。
- 实况照片：78 对照片 + 视频自动配对，视频部分隐藏。
- ML 使用 `CUDAExecutionProvider`；人脸 142 个、智能搜索 139 条。
- 视频转码日志显示 `NVENC-accelerated encoding and decoding`。
- 存储模板生效：文件落在 `library/admin/年/年-月-日/原文件名`。
- 注意：`TZ=America/Los_Angeles` 下，接近午夜的照片会落在和旧备份不同的日期文件夹（旧实例是 UTC），属正常。
- 13 个实况照片的视频部分上传后留在 `upload/`（合并隐藏时存储模板跳过了）。手动运行一次「存储模板迁移」任务（`PUT /api/jobs/storageTemplateMigration {"command":"start"}`）后全部归位。**正式导入完成后要跑一次这个任务。** 原因推测：实况照片的照片和视频分开上传，视频被合并隐藏时它自己的移动步骤被跳过（日志里有「文件找不到」的竞争警告）。文件在数据库里记录正确，不影响使用，但只备份 `library/` 会漏掉它们，所以备份范围要包含 `upload/`（见第 7 节第 9 步）。

---

## 6.5 导入结果（2026-09-30）

- 两个 immich-go 并行导入：A（`immich-backup`，2000–2022）、B（`immich-backup2`，2023–2026）。主体 2026-09-29 18:00 开始，2026-09-30 10:29 完成（含补传）。
- **最终核对**：备份盘 146,875 个文件 = 146,245 个照片/视频 + 629 个 `.xmp` 附属文件（随照片一起上传，不单独算资源）+ 1 个 `.immich` 标记。A 86,137 + B 60,108 = 146,245，最终补传两边都 0 错误、退出码 0。
- 未单独入库的：1 个压缩版小文件（`2017-03-28/2016-03-26 130612.jpg`，121 KB，同名同时间的 752 KB 版本已在库）；另有 9 个库里原本的小版本被 immich-go 用更大的版本替换（「server asset upgraded」）。
- 遇到并解决的问题：
  - 补传前有 74 个文件失败，主要是 2021 年 DJI 大视频：服务器高负载下 20 分钟内没响应（`Client.Timeout exceeded`）。补传改用 `--concurrent-tasks=4 --client-timeout=2h` 后全部成功。
  - immich-go 只要中途出过错，最后就返回退出码 1（即使 `--on-errors=continue`），可以借此判断是否需要再补传一遍。
  - 看守脚本 `import_watchdog.py` 每 20 分钟检查：自动重启中断的导入、恢复被暂停的队列、显存报错过多时重启 ML 容器（当晚重启了 6 次）。它在收尾时因为「存储模板迁移已在运行」（HTTP 400）退出，收尾步骤已手动完成。
- 导入后的后台处理（缩略图、智能搜索、人脸、OCR、转码、存储模板迁移）积压很多，瓶颈是 sda：WD40EZAZ 是 **SMR 硬盘**，大量写入后读延迟高达约 380 ms，CPU 大部分时间空闲。预计要几天才能处理完，不影响使用。
- 2026-09-30 用户在 Immich 里手动清理了约 1.3 万个资源（在回收站中，30 天内可恢复）。

## 6.6 sda 卡顿与 I/O 错误（2026-10-01 / 10-02）

- 现象：队列看起来「挂了」，存储模板迁移从 9-30 起不动；内核日志 10-01 14:10、18:45 两次 `Aborted Command`（命令 31 秒无响应）→ SATA 链路重置 → `I/O error, dev sda`（共 11 个读失败），Immich 里少量 RAW 缩略图报 `Input/output error`。
- SMART（10-02）：PASSED；Reallocated / Pending / Offline_Uncorrectable / UDMA_CRC 全为 0，32°C。**硬盘健康、不是线材问题**。
- 结论：WD40EZAZ 是 SMR 盘，导入 1.5 TB 后又被高并发随机读，盘内部整理数据时停顿超过内核默认 30 秒超时。
- 处理：缩略图 / 元数据 / 附属文件并发降为 2，读延迟从约 380 ms 降到约 56 ms。
- 备选：把 SCSI 超时调到 180 秒（`echo 180 | sudo tee /sys/block/sda/device/timeout`，重启后失效，要持久化需 udev 规则）。

## 7. 剩余步骤

1. ~~第二份备份~~：已完成并核对，已改名 `immich-backup2`。
2. ~~测试实例~~：已完成并删除。
3. ~~格式化 sda~~：已完成（`sudo bash format-wd-ext4.sh`，脚本在本仓库）。
4. `docker compose up -d`，注册管理员，创建 API Key，运行 `./apply-settings.py` 应用 `immich-settings.json`。
5. ~~两个 immich-go 并行导入~~（已完成，见 6.5 节；测速：两盘单独读照片 54–64 MB/s，同时读合计约 190 MB/s）：`immich-backup` → 2000–2022（86,137 个文件，743 GB），`immich-backup2` → 2023–2026（60,737 个文件，751 GB）。不开启 RAW/JPG、连拍堆叠。
6. ~~运行「存储模板迁移」任务~~（已触发，后台处理中），把实况照片的视频部分移入 `library/`。然后核对：Immich 里的资源数应与备份盘文件数一致（146,875 个文件，实况照片的视频部分会被隐藏合并）。
7. 等缩略图、人脸识别、转码跑完（1–2 天），再用 `rsync --delete` 以新库重建 `immich-backup`、`immich-backup2`（新库目录结构与旧备份不完全相同）。
8. 可选：根据 `immich_import_A.csv` 用 API 重建相册。
9. 设置定期备份：**备份整个 `UPLOAD_LOCATION` 的原始文件目录**，而不只是 `library/`（有些文件，比如实况照片的视频部分，可能暂时留在 `upload/`）：
   `rsync -rt --partial --exclude=thumbs --exclude=encoded-video /mnt/data/immich/ <备份盘>/immich/`
   外加数据库备份（Immich 自带的每日 `pg_dump` 在 `/mnt/data/immich/backups/`，会随上面的 rsync 一起备份）。

---

## 8. 注意事项

- 照片库目前有两份：`immich-backup`（已核对）+ `FYQ-LU`（同步中）。**格式化 sda 前两份都要核对完成**。
- sda 无分区表，Windows 下显示 unallocated 属正常，不要初始化。
- Postgres 数据库只能放 SSD（ext4），不能放 NTFS/exFAT/网络共享。
- Immich 不会扫描 `UPLOAD_LOCATION` 来重建索引，内部库的真相来源是数据库，所以数据库也要定期备份。
- 备份策略（3-2-1）：原库（sda）+ `immich-backup`（家里）+ `immich-backup2`（异地）。

---

## 9. 历史：原方案（2026-09-28，已废弃）

原计划是保留 NTFS，把原图移到 `/mnt/data/originals-until-20260531/`，以只读方式挂载为 External Library，新的上传放 `/mnt/data/immich`。废弃原因：见第 4 节。
