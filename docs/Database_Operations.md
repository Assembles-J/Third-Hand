# SQLite 数据库备份、恢复与迁移

阶段 0 的工具不改变业务表或 API 行为。执行前应停止后端写入，或将备份文件复制到独立位置后再操作。

从 `backend/` 目录执行迁移登记（可重复执行）：

```powershell
..\.verify-venv\Scripts\python.exe -m app.migrations --database data\third_hand.db
```

首次执行会登记当前版本的迁移（包括历史 schema 基线及新增 Context 表）；再次执行不会重复应用已登记的迁移。

创建经过 SQLite 完整性校验的备份：

```powershell
..\.verify-venv\Scripts\python.exe scripts\database_backup.py data\third_hand.db ..\backups\third_hand-YYYYMMDD.db
```

恢复先写入一个不存在的新文件，校验后再由运维人员替换应用实际使用的数据库文件：

```powershell
..\.verify-venv\Scripts\python.exe scripts\database_backup.py --restore ..\backups\third_hand-YYYYMMDD.db ..\restore\third_hand.db
```

这两个命令均拒绝覆盖既有目标文件，以避免误覆盖生产数据。
