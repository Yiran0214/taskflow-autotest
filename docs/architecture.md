# TaskFlow 自动化测试框架架构文档

## 1. 总体设计

五层架构,依赖单向向下,新增用例只需触达"用例层":

```
用例层 (testcases/)
   ├── API 用例 ──→ API 封装层 (api/) ──→ 公共层 (common/) ──→ 配置层 (config/)
   └── UI 用例 ──→ Page Object 层 (pages/) ──→ 公共层
                         │                        │
                    pytest-playwright           requests/loguru
                         │                        │
                         └────── 被测系统 TaskFlow ←┘
```

设计原则:

1. **测试代码即文档**:业务 API 以 `@allure.step` 封装成中文业务动作,用例可读性优先
2. **被测系统自给自足**:local 环境框架自动拉起服务,克隆即跑,零部署成本
3. **隔离优先**:用户级、客户端级、服务级三层隔离,保证并行与重跑安全
4. **失败可诊断**:截图 + Trace + 日志三重证据自动归档

## 2. 关键机制详解

### 2.1 被测服务自动拉起(local 环境)

```
app_server fixture (session)
  ├── 生成临时 SQLite 路径 (tmp_path_factory, 会话结束自动清理)
  ├── 子进程拉起: uvicorn app.main:app --port <port>
  │     └── 注入环境: TASKFLOW_DB / TASKFLOW_SECRET_KEY / PYTHONIOENCODING
  ├── 轮询 /health 就绪探测 (30s 超时, 失败输出服务日志)
  └── teardown: terminate → wait(10s) → kill 兜底
```

- 测试与开发数据库**物理隔离**,测试永不污染开发数据
- 通过 `config.yaml` 的 `use_external_server` 一键切换为指向已部署服务(test/ci 环境)

### 2.2 并行执行端口偏移(pytest-xdist)

并行时每个 worker 拥有独立的 session fixture 实例,各自拉起服务:

| worker | 端口 | 数据库 |
|--------|------|--------|
| gw0 | 8001 | worker 专属临时库 |
| gw1 | 8002 | worker 专属临时库 |
| gw2 | 8003 | ... |

实现要点:

- `worker_id` fixture(非 xdist 时为 `"master"`)解析出编号,`base_url` 端口做对应偏移
- `base_url` fixture **声明依赖 `app_server`**,保证偏移生效后才取值(pytest fixture 依赖顺序保证)
- `--dist loadscope` 按模块分配用例,同一模块的 session 状态不被跨 worker 撕裂

### 2.3 客户端隔离与 token 管理

```
client (session, 匿名)         ── 注册/预置数据
api_client_factory (function)  ── 每次调用返回全新实例, 用例结束统一关闭
  ├── auth_client:  登录态客户端 (每用例独立)
  └── anon_task_api: 匿名客户端 (确保无 token 残留)
```

**为什么必须独立实例**:JWT 是客户端级状态。若两个已登录用户共享一个实例,后登录者的 token 会覆盖前者,"越权访问"用例将无法构造出真实的多用户场景(这是本项目踩过并显式设计规避的坑)。

### 2.4 UI 失败自诊断链路

```
pytest_runtest_makereport (hook)
  └── call 阶段失败 → 标记 item._taskflow_failed
        ↓
page fixture teardown
  ├── 全页截图  → reports/screenshots/<用例>.png → Allure 附件
  ├── Trace     → reports/traces/<用例>.zip → playwright show-trace 可回放
  └── 执行日志  → pytest_sessionfinish 归档到 Allure (KeyError 静默兜底)
```

截图/Trace 在 CI 中作为 artifact 归档,并随报告页发布到 GitHub Pages。

### 2.5 前端竞态防护(被测系统的可测性设计)

UI 自动化用例发现的前端竞态问题,修复方案本身也成为被测系统的设计亮点:

```js
let loadSeq = 0;                          // 请求序号
async function loadTasks() {
  const mySeq = ++loadSeq;                // 发起时递增并记录
  const { status, data } = await request('GET', `/tasks${q}`);
  if (status !== 200 || mySeq !== loadSeq) return;  // 过期响应直接丢弃
  ...
}
```

快速切换筛选/连续操作时,晚到的旧响应因序号不匹配被丢弃,保证页面永远渲染最新状态。

## 3. 配置体系

三级优先级(高→低):

```
命令行 --env  >  环境变量 TEST_ENV (选环境)
TEST_<KEY>    >  config.yaml <env> 小节 (覆盖任意键)
```

`TEST_BASE_URL=http://app:8001` 这类覆盖使同一套代码零改动跑在任意环境,是 docker-compose 与 CI 复用的基础。

## 4. 断言体系

| 工具 | 位置 | 职责 |
|------|------|------|
| `assert_status` | common/assertions.py | 状态码断言,失败信息带响应体 |
| `validate_schema` | common/assertions.py | 轻量 JSON Schema 校验(支持 `str\|none` 等联合类型、嵌套对象、数组元素) |
| `assert_task_shape` | common/assertions.py | 任务响应结构断言(字段类型 + 枚举值) |
| Playwright expect | pages/* | UI 自动等待断言(可见性/文本/数量/URL) |
| 落库断言 | testcases 内 db fixture | 直连 SQLite 验证持久化一致性 |

不引入 jsonschema 等重依赖的原因:被测系统为自建,响应契约稳定,轻量校验器足够且零学习成本 —— 这是"按需造轮子"的取舍,面试可展开说明。

## 5. 扩展指南

- **新增 API 用例**:在 `api/` 加一个 @allure.step 方法 → 在 `testcases/api/` 写用例 → 完成
- **新增 UI 用例**:在 `pages/` 加页面对象(元素统一 data-testid)→ 写旅程用例
- **新增环境**:config.yaml 加一节 → 完成(TEST_* 覆盖自动生效)
- **多浏览器**:pytest-playwright 参数化 `browser_name`,框架无其他改动
- **接真实业务系统**:替换 base_url 指向 + 按真实接口重写 `api/` 层,框架层零改动
