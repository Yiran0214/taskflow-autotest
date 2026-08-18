# TaskFlow 项目面试速成:高频问答 50 题

> 用法:Day 4 背 Part 1 与 Part 3,零散时间刷 Part 2。答案里 `file:行号` 可回代码确认。
> 原则:**答案必须结合本项目讲,不要背通用八股** —— 面试官想听的是"你怎么做的"。

---

## Part 1 必考 10 题(每题含追问预案,需脱稿)

### Q1 介绍一下这个项目的整体架构

**标准答**:项目分两大块 —— 自建被测系统 TaskFlow(FastAPI + SQLite 的任务管理 Web 应用,原生 JS 前端),和五层自动化测试框架(配置层 config / 公共层 common / API 封装层 api / Page Object 层 pages / 用例层 testcases)。依赖单向向下,新增用例只需要动用例层。工程化上有 run.py 统一入口、Docker 容器化、GitHub Actions 流水线发布 Allure 报告。

**追问预案**:
- *为什么被测系统要自己搭?* → 三点:①测试对象可控可造数,不依赖第三方网站(第三方改版/反爬会导致用例全挂);②可以在系统里做可测性设计(data-testid、竞态守卫);③真实发现 8 个缺陷,证明自动化创造价值
- *为什么分五层?* → 职责单一:配置只管环境,公共层管请求与断言,api/pages 管业务封装,用例层只描述场景。新增用例零成本,业务接口变化只改封装层

### Q2 为什么用 pytest 而不是 unittest?

**标准答**:三个核心优势:①fixture 机制 —— 服务拉起、数据准备、客户端注入都是 fixture,支持依赖和 scope 管理,unittest 做不到;②插件生态 —— xdist 并行、rerunfailures 重试、playwright、allure 都是 pytest 插件,接入零成本;③参数化 —— 边界值用例用 `@pytest.mark.parametrize` 数据驱动,一条用例覆盖一组数据。

**追问预案**:*unittest 也能写自动化,差在哪?* → 承认能写,但 fixture 依赖管理、并行、报告这些工程能力都要自己造,而 pytest 开箱即用,团队效率差别大。

### Q3 fixture 的作用域有哪些?你在项目里怎么用的?

**标准答**:function / class / module / package / session。项目里三层都用到了:session 级放"昂贵且可复用"的 —— app_server(被测服务只拉一次)、client、browser;function 级放"必须每次新建"的 —— user(每个用例独立随机用户)、page(每个用例独立浏览器上下文)。

**追问预案**:
- *为什么登录态客户端用工厂函数而不是 fixture?* → 因为 token 是客户端级状态:如果两个已登录用户共享一个实例,后登录者的 token 会覆盖前者,越权用例就测不出真实的多用户场景。所以 `api_client_factory` 每次调用返回全新实例(`testcases/conftest.py`)
- *session 级 fixture 在并行下会不会冲突?* → 会,所以做了端口偏移:每个 worker 的 app_server 用 `worker_id` 编号偏移端口(gw1→8002),独立临时数据库

### Q4 被测服务是怎么拉起来的?为什么要自动拉起?

**标准答**:local 环境下,app_server fixture 用 subprocess 拉起 uvicorn 子进程,注入 TASKFLOW_DB 指向临时 SQLite、TASKFLOW_SECRET_KEY 等环境变量,然后轮询 /health 就绪探测(30s 超时,失败输出服务日志),测试结束 terminate 回收。好处:①开发者克隆即跑,不需要部署任何东西;②临时数据库与开发数据物理隔离,测试永不污染开发环境;③测试数据可预测。

**追问预案**:*万一服务起不来怎么排查?* → 日志已重定向到 logs/server-*.log,超时异常会带上日志路径;本地可直接 `python run.py server` 复现。

### Q5 并行执行怎么做的?遇到过什么问题?

**标准答**:pytest-xdist `-n 4 --dist loadscope`(按模块分配,同一模块 session 状态不被撕裂),全量 64 用例从串行 13s 提到并行 10s。遇到的真实问题:**端口冲突** —— 每个 worker 都要拉起自己的被测服务,都抢 8001。解决:worker_id 编号做端口偏移(gw0→8001、gw1→8002),同时 base_url fixture 声明依赖 app_server,保证偏移生效后再取值。

**追问预案**:*为什么不直接让所有 worker 连同一个服务?* → 数据会互相污染(每个 worker 独立数据库是隔离前提),而且单点服务会成为瓶颈;各 worker 独立服务 + 独立库才能保证用例互不干扰。

### Q6 UI 用例失败了你怎么定位?

**标准答**:三重证据自动归档:①pytest hook(makereport)标记失败用例,page fixture teardown 自动保存全页截图;②同时保存 Playwright Trace(zip,包含每一步 DOM 快照/网络/控制台),`playwright show-trace` 可逐步回放;③执行日志随报告归档进 Allure。流程:看报告红用例 → 打开截图确认现象 → 回放 Trace 定位是哪一步开始错的。

**追问预案**:*Playwright 自动等待和 sleep 有什么区别?* → 断言用 expect 自动重试(默认 5s 超时)等待元素状态,不用 sleep:sleep 固定时长要么浪费要么不稳,自动等待只在状态满足时立刻通过,稳定且快。

### Q7 讲一个你发现的最有价值的 bug(用 STAR 法)

**标准答**(BUG-03,背熟):
- **S 场景**:UI 用例模拟连续快速添加 3 个任务
- **T 任务**:验证快速操作下输入不丢失
- **A 行动**:断言发现只创建了 2 个 → 分析前端代码:添加任务后要**等接口返回才清空输入框**,而用户此时已输入了下一个任务,清空动作把新输入覆盖了 → 修复:点击提交**立即清空**,接口失败时再恢复用户输入 → 补回归用例固化成断言
- **R 结果**:快速连续创建不再丢内容,用例转绿并长期回归
- **亮点**:这是典型的"竞态/时序类缺陷",接口测试发现不了,只有真实交互的 UI 自动化能发现 —— 证明 UI 自动化的价值

**追问预案**:*为什么接口测试发现不了?* → 接口单次调用没有"连续操作时序",且前端清空输入框是纯前端行为,后端无感知。

### Q8 接口自动化都断言什么?为什么还要做落库断言?

**标准答**:三层断言:①状态码(assert_status,失败信息带响应体);②响应结构 —— 自研轻量 JSON schema 校验器校验字段类型/枚举值(支持 `str|none` 联合类型);③业务正确性 —— 本地模式直连临时 SQLite 做落库断言,验证接口响应与数据库持久化一致(如 test_create_persisted_in_db、test_status_flow_persisted)。落库断言的意义:接口"响应正确"不等于"数据正确",响应可能是缓存/伪造的;直连数据库双重验证才是端到端可信。

**追问预案**:*为什么不用 jsonschema 库?* → 被测系统自建、响应契约稳定,轻量校验器够用且零学习成本;如果接第三方复杂契约再引入 jsonschema,这是按需造轮子的取舍。

### Q9 CI 流水线怎么设计的?

**标准答**:GitHub Actions 三阶段:api-tests 和 ui-tests 两个 job 并行跑(UI job 额外装 chromium),各自上传 allure-results 和失败截图/Trace artifact;report job 合并结果、用 allure CLI 生成报告、发布到 GitHub Pages(在线可访问,附截图回放);performance job 手动触发跑 Locust。触发:push/PR 到 main + 每日定时回归(UTC 18:30)。

**追问预案**:*为什么性能测试要手动触发?* → 压测消耗资源和时长,每次 push 都跑不划算;功能回归高频、性能回归低频,按需触发是工程上合理取舍。*为什么报告发 Pages?* → 报告对全团队可见(链接即分享),不用登录 CI 找 artifact;失败截图/Trace 也随报告上线,远程定位问题。

### Q10 性能测试怎么做的?关注什么指标?

**标准答**:Locust 建模 4 类场景 —— 查询列表(权重 4)、创建(2)、统计(1)、完整生命周期(1),每个虚拟用户 on_start 独立注册+登录携带真实 JWT 会话,等待时间 1-3s 随机。关注指标:吞吐 RPS、响应时间 P95/P99、错误率;冒烟验证 5 并发 52 请求 0 失败,列表查询平均 3ms。

**追问预案**:*为什么场景要配权重?* → 模拟真实用户行为分布:读多写少。压测模型越接近真实流量,发现的瓶颈越有说服力。*如何确定并发数?* → 阶梯加压:从低并发逐步提升找拐点,而不是一步到位。

---

## Part 2 快速题 40 道(每题能讲 2~4 句即可)

### Python 基础

| # | 问题 | 答题要点 |
|---|------|---------|
| 1 | 装饰器是什么?项目里哪些是装饰器? | 接收函数返回新函数;项目:allure.step/title、pytest.mark、fixture |
| 2 | yield 和 return 的区别?fixture 为什么用 yield? | yield 挂起保留现场,可恢复执行 —— fixture 用 yield 分割 setup 和 teardown,用例结束继续执行清理 |
| 3 | 类继承在项目里的体现? | BasePage 封装 goto/等待/定位,LoginPage/TaskPage 继承复用 |
| 4 | 异常处理怎么用的? | 截图/日志等非关键路径 try/except 兜底,失败不影响用例清理;服务就绪探测捕获 RequestException 重试 |
| 5 | with 上下文管理器? | ApiClient.close 统一关闭 requests Session;db fixture 的 sqlite3 连接 |
| 6 | *args/**kwargs 项目哪里用了? | task_api.list(**params) 透传查询参数;expect_stats(**kwargs) 批量断言统计看板 |
| 7 | 可变类型默认参数的坑? | 列表/字典作默认参数会被所有调用共享,要用 None;项目 ApiClient 工厂函数返回新实例避免共享状态 |
| 8 | 深拷贝/浅拷贝? | 浅拷贝只复制引用(嵌套对象共享);测试数据造数时注意别让用例共享同一可变对象 |
| 9 | 列表推导式? | 项目里 all_inner_texts 结果处理;比 for 循环简洁 |
| 10 | lambda?项目里哪里用? | 短函数;如事件绑定/简单转换,保持一行可读 |

### pytest / 框架

| # | 问题 | 答题要点 |
|---|------|---------|
| 11 | pytest.ini 里配置了什么? | testpaths、pythonpath、addopts(含 --alluredir)、markers 注册 |
| 12 | 数据驱动怎么实现的? | parametrize + YAML(testdata/users.yaml 边界值数据),用例名里带 case[name] 中文标识 |
| 13 | conftest.py 的作用? | 同级及子目录共享 fixture/hook;我们的服务拉起、客户端、截图 hook 都在 testcases/conftest.py |
| 14 | 怎么只跑 API 用例? | markers + run.py --type api(或 -m api) |
| 15 | rerunfailures 什么原理?什么时候用? | 用例失败后自动重跑指定次数,通过则计为通过;过滤环境抖动,不掩盖真 bug(重跑也失败的仍报红) |
| 16 | 装了哪些 pytest 插件? | xdist 并行、rerunfailures 重试、playwright、allure-pytest 报告、pytest-html 兜底 |
| 17 | hook 是什么?项目里用了哪个? | pytest 生命周期钩子;pytest_runtest_makereport 标记 call 阶段失败,供 page fixture 决定截图 |
| 18 | 用例怎么保证独立性? | 每用例独立随机用户、独立客户端实例、临时数据库,不依赖执行顺序,任意重跑安全 |
| 19 | fixture 依赖怎么写?为什么 base_url 依赖 app_server? | 签名里直接写 fixture 名;pytest 按依赖先实例化 app_server —— 并行端口偏移生效后 base_url 才能取到新端口 |
| 20 | 断言失败信息怎么设计? | assert_status 失败时附响应体,一眼看到服务端报错;UI 断言自动等待 5s 超时输出期望/实际 |

### 接口测试

| # | 问题 | 答题要点 |
|---|------|---------|
| 21 | requests 封装了什么? | 统一 base_url、timeout、token 注入(Authorization header)、请求日志(method/path/status/耗时)、session 复用 |
| 22 | 接口测试测什么?字段怎么校验? | 状态码 + 响应结构(schema 校验类型/枚举)+ 业务值(落库断言);不只看 200 |
| 23 | 401/403/404 的区别?为什么越权返回 404? | 401 未认证、403 已认证但无权限;越权用 404 是安全设计 —— 隐藏资源存在性,不让攻击者探测资源 ID |
| 24 | JWT 是什么?怎么测过期 token? | Header.Payload.Signature 三段,服务端签名校验;测试用本地同密钥自签过期时间戳的 token,断言 401 + 固定错误信息 |
| 25 | 幂等性怎么测? | 重复注册同用户名 → 409;删除同一任务两次 → 404;断言第二次调用结果可预期 |
| 26 | 状态码设计? | 201 创建、204 删除无内容、401 未认证、404 不存在/越权、409 冲突(重名/终态流转)、422 参数校验失败 |
| 27 | 参数校验 422 怎么测? | 边界值 + 非法类型 + 缺字段(parametrize 一组用例),断言 detail 定位到具体字段 |
| 28 | 状态机怎么测的? | 全路径 pending→in_progress→done + 非法流转(如 in_progress→pending 422)+ done 终态转出 409 + 落库状态一致 |

### UI / Playwright

| # | 问题 | 答题要点 |
|---|------|---------|
| 29 | Playwright 比 Selenium 的优势? | 自动等待、多浏览器同 API、Trace 回放、网络拦截;启动快,无 webdriver 版本匹配问题 |
| 30 | 自动等待怎么实现? | expect 默认 5s 轮询重试直到条件满足;项目里 expect_stats 用 to_have_text 等统计看板异步渲染 |
| 31 | 为什么用 data-testid 定位? | 与样式/文本/结构解耦,前端改版不影响;这是被测系统"可测性设计"的一部分 |
| 32 | 截图和 Trace 怎么保存的? | makereport hook 标记失败 → page fixture teardown 存 reports/screenshots、reports/traces → allure 附件;Trace 用 playwright show-trace 回放 |
| 33 | 多浏览器怎么扩展? | pytest-playwright 参数化 browser_name,框架零改动;当前只跑 chromium 是执行时长取舍 |
| 34 | POM 的优缺点? | 优点:元素定位单点维护、用例只描述业务;缺点:页面复杂时对象膨胀 —— 按模块拆分页面类 |

### CI / Docker / 工程

| # | 问题 | 答题要点 |
|---|------|---------|
| 35 | GitHub Actions 结构? | workflow 由 job 组成,触发:push/PR/schedule/workflow_dispatch;concurrency 防止重复排队 |
| 36 | Allure 报告怎么发布的? | allure CLI 生成静态站 → upload-pages-artifact → deploy-pages 发布到 GitHub Pages,报告 URL 稳定可分享 |
| 37 | Dockerfile 分层缓存? | 依赖文件先 COPY 再 pip install,改代码不重装依赖;PLAYWRIGHT_BROWSERS_PATH 固化浏览器目录 |
| 38 | docker-compose 编排了什么? | app(被测服务 + healthcheck)+ tests(依赖健康后跑测试,TEST_BASE_URL 指向容器网络) |
| 39 | 多环境怎么切换? | config.yaml 三节(local/test/ci)+ TEST_ENV 选择 + TEST_<KEY> 覆盖任意键;优先级:命令行 > 环境变量 > YAML |
| 40 | loguru 好在哪? | 一行配置、自动滚动、颜色分级;setup_logger 幂等设计防止重复初始化 |

---

## Part 3 答题技巧

### 1. 缺陷讲述模板(STAR,以 BUG-03 为例背熟)

> "讲一个我印象最深的缺陷:我在写 UI 用例时模拟**连续快速添加 3 个任务**,断言发现只创建了 2 个 —— 任务 B 的内容丢了。我分析前端代码发现:添加按钮的点击处理是**等接口返回才清空输入框**,这期间用户已经输入了下一个任务,清空动作把新输入覆盖了。修复方案是**提交时立即清空、接口失败时恢复输入**。修复后用例转绿,并作为回归用例固化了。这个缺陷接口测试是发现不了的 —— 它是前端时序问题,单次接口调用没有'连续操作'的概念,这正是 UI 自动化不可替代的价值。"

### 2. 不会的题怎么答

模板:"这个点我在项目里**没有深入过**,但我知道它和 XX 相关……" → 立即关联到会的内容。
**绝对不要**:装懂、沉默、说"老师换一题"。
示例:被问"xdist 底层怎么分发用例的?" → "底层实现我没读过源码,但我在用的时候解决过它带来的真实问题:每个 worker 会独立拉起被测服务导致端口冲突,我用 worker_id 做了端口偏移。"

### 3. 挖坑题识别与标准答

| 坑 | 标准答 |
|----|--------|
| "你的项目有什么不足?" | 三点真诚短板:①只跑了 chromium,多浏览器矩阵未展开;②UI 用例只有 9 条,关键旅程覆盖但非穷举;③没有接入代码覆盖率门禁。**然后补一句改进方向** |
| "为什么不做得更多?" | "测试广度与维护成本要平衡:UI 用例每多一条都是长期维护成本,我把穷举放在 API 层,UI 层只保关键旅程" |
| "用例会不会误报?" | "有 rerunfailures 重试过滤环境抖动,重试仍失败才报红;截图+Trace 保证每例失败都有证据" |

### 4. 反问环节问什么

- "团队目前的自动化覆盖到什么程度?框架是自研还是开源封装?"
- "岗位的日常是偏用例设计还是偏框架建设?"
- "自动化用例在 CI 里的通过率要求是多少?"

### 5. 面试前一天清单

- [ ] `python run.py test` 完整跑一遍(确认 64 绿,也顺便再熟悉报告)
- [ ] `allure serve reports/allure-results` 过一遍 64 个用例标题
- [ ] 背熟 Part 1 的 Q1/Q5/Q7/Q8(命中率最高)
- [ ] 把 docs/ 四份文档目录扫一遍,知道每份讲什么
- [ ] 打开 GitHub 仓库看 Actions 页面(投递前推上去,面试官会看仓库)
