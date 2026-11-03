# Ops Task Demo

一个轻量级任务管理应用，用来验证 Kubernetes 平台的应用交付、持久化和可观测性能力。它不是监控平台，不重复实现 Prometheus / Grafana / Loki 的职责。

## 功能

- 任务创建、列表、状态更新、删除
- SQLite 持久化到 `/data/tasks.db`
- `/health`：存活探针
- `/ready`：就绪探针（检查数据库连接）
- `/metrics`：Prometheus 指标，包括 HTTP 请求数、任务创建/完成数、当前任务数
- JSON 结构化日志，输出到 stdout，供容器日志采集系统收集
- 非 root 用户运行、只读根文件系统、资源 requests/limits

## 架构

```text
Developer
   |
   | git push
   v
GitHub Actions
   |
   | ARC self-hosted runner: docker build
   v
Harbor (image: commit SHA)
   |
   | workflow updates k8s/deployment.yaml
   v
GitHub GitOps manifests
   |
   | Argo CD auto-sync
   v
Kubernetes Deployment -> Service -> Envoy Gateway / HTTPRoute
                 |
                 +-> Longhorn PVC -> SQLite data
                 |
                 +-> ServiceMonitor -> Prometheus -> Grafana
                 |
                 +-> stdout JSON logs -> Promtail -> Loki
```

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data
DB_PATH=./data/tasks.db flask --app app run --host 0.0.0.0 --port 8080
```

浏览器访问 `http://127.0.0.1:8080`。

## 本地容器验证

```bash
docker build -t ops-task-demo:local .
docker run --rm -p 8080:8080 -v "$PWD/data:/data" ops-task-demo:local
```

## Kubernetes 部署

先确认集群有名为 `longhorn` 的 StorageClass：

```bash
kubectl get sc
```

然后：

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl -n task-demo get pods,pvc,svc
```

首次部署前，将 `k8s/deployment.yaml` 的镜像替换成已推送到 Harbor 的实际镜像标签。确保集群节点信任 Harbor 的证书，并配置所需 imagePullSecret（若 Harbor 项目为私有）。

临时访问：

```bash
kubectl -n task-demo port-forward svc/task-demo 8080:80
```

再访问 `http://127.0.0.1:8080`。

## CI/CD 配置

当前工作流采用你现有环境验证过的 Pure CI Pipeline 写法：

- Runner label：`my-runners`
- Git 代理：`http://192.168.31.115:7890`
- Harbor：`harbor.k8s.local:32078`
- Harbor 项目：`myapp`
- 镜像名：`ops-task-demo`
- 镜像 tag：Git commit SHA 前 7 位
- Harbor CA：Runner 上预先放置 `/tmp/harbor-ca/ca.crt`

GitHub 仓库需要配置 Secrets：

- `HARBOR_USERNAME`
- `HARBOR_PASSWORD`

**Runner 前置条件：**

1. Runner 执行环境可以访问 GitHub，且代理 `192.168.31.115:7890` 可用。
2. Runner 主机上存在 `/tmp/harbor-ca/ca.crt`，内容是 Harbor 服务端证书对应的 CA 证书。
3. Runner 使用的 Docker daemon 能访问 `harbor.k8s.local:32078`；如果 Docker daemon 实际运行在 DinD sidecar 中，证书必须安装到那个 daemon 对应的证书目录/容器，而不只是 runner 容器的 `$HOME`。
4. Runner 已安装 Docker CLI，且 Docker daemon 可用。
5. Harbor 项目 `myapp` 已创建，凭据有 push 权限。

工作流只负责 **CI：构建并推送镜像**，不在本次 workflow 中修改 Kubernetes manifest，也不自动触发 Argo CD 更新。这样先保持你已验证的 CI 边界，后续再单独接 GitOps 更新流程。

不要通过关闭 TLS 校验来绕过证书问题。

## Prometheus

`k8s/servicemonitor.yaml` 是 kube-prometheus-stack 的 ServiceMonitor 示例。确认 Prometheus 的 `serviceMonitorSelector` 与 `release: kube-prom` 标签匹配；不匹配时按实际 Helm release / selector 修改。

## Envoy Gateway

`k8s/httproute.yaml` 是模板，必须先把 `YOUR_GATEWAY_NAME`、域名和 Gateway namespace 改成你集群中的实际值，再单独 apply。不要直接应用占位模板。

## 资源与边界

- 建议先保持 1 个副本：SQLite 不适合多个副本并发共享。
- Deployment 使用 `Recreate`，避免滚动更新期间两个 Pod 同时挂载同一个 RWO 卷。
- 该 Demo 是实验用途，不是生产级多租户任务系统。
- SQLite + Longhorn RWO 适合验证 PVC 与数据持久化，不代表高可用数据库方案。
- 该应用构建很轻，但不要在 node01 已经出现内存 / I/O 压力时反复触发构建。
- 监控、日志和存储仍由平台组件承担；应用只暴露业务指标和结构化日志。

## 建议验收

1. 创建任务，确认列表显示。
2. 更新任务状态，确认状态变化。
3. 删除任务，确认任务消失。
4. 删除 Pod，确认 PVC 中数据仍存在。
5. 访问 `/health`、`/ready`、`/metrics`。
6. 在 Prometheus 查询 `http_requests_total`、`tasks_created_total`。
7. 在 Loki 查询 `{namespace="task-demo"}`（按实际标签调整）。
8. 修改页面文字并 push，观察 Actions 构建、Harbor 新 tag、GitOps manifest 更新、Argo CD 同步。
9. 观察 Deployment rollout 和 Grafana 指标变化。

## 项目定位

该项目用于证明云原生平台能够交付一个有真实业务逻辑、持久化、健康检查、指标和结构化日志的应用。重点是平台工程与运维，不是业务功能复杂度。
