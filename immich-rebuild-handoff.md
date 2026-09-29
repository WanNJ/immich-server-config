# Immich 服务器重建 — 交接说明

生成日期：2026-09-28　｜　最后更新：2026-09-29
机器：jackwan-X570-AORUS-ELITE

> **2026-09-29 更新摘要**：方案从「NTFS 原盘 + External Library」改为「WD 盘格式化为 ext4 + 用 immich-go 从备份盘导入到内部库」。
> 原因：备份盘已就绪（空间问题不复存在），ext4 读照片比 ntfs-3g 快 3–4 倍。目标版本 v3.2.4（原文写的 v3.2.0 已过时）。
> 旧方案保留在第 9 节作为历史记录。

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
| `sda` | WD40EZAZ，WD-WX72D22ESR5C（内置 SATA） | 3.7 TB | **NTFS（无分区表）**，`immich-disk` | `/mnt/data` | Immich 照片库 → **待格式化为 ext4** |
| `sdb` | Seagate BUP Slim WH，NA7Z04Q5（USB） | 1.8 TB | ext4，`immich-backup` | `/media/jackwan/immich-backup` | 照片库完整副本 1（已核对） |
| `sdd` | Seagate BUP Slim RD，NA7WAZGF（USB） | 1.8 TB | ext4，`FYQ-LU` → 待改名 `immich-backup2` | `/media/jackwan/FYQ-LU` | 照片库副本 2（同步中），之后放异地 |
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

- 存储模板：开启，`{{y}}/{{y}}-{{MM}}-{{dd}}/{{filename}}`（与旧库目录结构一致）。
- 视频转码：硬件加速 `nvenc`，开启硬件解码。

### 测试结果（2026-09-29，SSD 临时实例，220 个文件）

- immich-go 上传 220/220，0 错误；照片、RAW（DNG）、视频、实况照片都正常。
- 实况照片：78 对照片 + 视频自动配对，视频部分隐藏。
- ML 使用 `CUDAExecutionProvider`；人脸 142 个、智能搜索 139 条。
- 视频转码日志显示 `NVENC-accelerated encoding and decoding`。
- 存储模板生效：文件落在 `library/admin/年/年-月-日/原文件名`。
- 注意：`TZ=America/Los_Angeles` 下，接近午夜的照片会落在和旧备份不同的日期文件夹（旧实例是 UTC），属正常。
- 13 个实况照片的视频部分上传后留在 `upload/`（合并隐藏时存储模板跳过了）。手动运行一次「存储模板迁移」任务（`PUT /api/jobs/storageTemplateMigration {"command":"start"}`）后全部归位。**正式导入完成后要跑一次这个任务。** 原因推测：实况照片的照片和视频分开上传，视频被合并隐藏时它自己的移动步骤被跳过（日志里有「文件找不到」的竞争警告）。文件在数据库里记录正确，不影响使用，但只备份 `library/` 会漏掉它们，所以备份范围要包含 `upload/`（见第 7 节第 9 步）。

---

## 7. 剩余步骤

1. **等 `FYQ-LU` 同步完成并核对**（照片库第二份副本）。然后改卷标：
   `sudo e2label /dev/disk/by-id/usb-Seagate_BUP_Slim_RD_NA7WAZGF-0:0-part1 immich-backup2`
2. ~~测试实例~~：已完成并删除。
3. **格式化 sda 为 ext4**（需要 sudo，按序列号 `WD-WX72D22ESR5C` 定位），更新 `/etc/fstab`：
   `UUID=<新UUID>  /mnt/data  ext4  defaults,noatime,nofail  0  2`，然后 `mkdir /mnt/data/immich && chown jackwan:jackwan`。
4. `docker compose up -d`，注册管理员，设置存储模板和 NVENC，创建 API Key。
5. 两个 immich-go 并行导入：`immich-backup` 导入一部分年份、`immich-backup2` 导入另一部分。
6. 运行「存储模板迁移」任务，把实况照片的视频部分移入 `library/`。然后核对：Immich 里的资源数应与备份盘文件数一致（146,875 个文件，实况照片的视频部分会被隐藏合并）。
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
