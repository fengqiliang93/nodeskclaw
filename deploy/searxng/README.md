# SearXNG Docker 部署

基于官方容器安装文档整理：

- 文档：`https://docs.searxng.org/admin/installation-docker.html#installation-container`
- 部署目录：`deploy/searxng/`
- 宿主机访问地址：`http://<searxng-host>:18080`
- K8s 集群内地址：`http://searxng-web.nodeskclaw-staging.svc.cluster.local:8080`

## 启动

```bash
cd deploy/searxng
docker compose up -d
```

## 停止

```bash
cd deploy/searxng
docker compose down
```

## 测试

```bash
curl -I http://127.0.0.1:18080
curl 'http://127.0.0.1:18080/search?q=searxng&format=json'
```

## K8s 集群内部署

AI 员工实例位于 K8s Pod 内，不能稳定访问节点 IP 端口，因此需要额外部署一套 ClusterIP 服务。
注意 Service 名不能叫 `searxng`，否则会和镜像使用的 `SEARXNG_PORT` 环境变量撞名：

```bash
sudo kubectl --context default apply -f deploy/searxng/k8s-cluster.yaml
sudo kubectl --context default rollout status deploy/searxng -n nodeskclaw-staging
```

集群内验证：

```bash
sudo kubectl --context default run searxng-probe --rm -it --restart=Never -n nodeskclaw-staging \
  --image=node:22-alpine -- \
  sh -lc "node -e \"fetch('http://searxng-web.nodeskclaw-staging.svc.cluster.local:8080/search?q=searxng&format=json').then(async r=>{console.log(r.status);console.log((await r.text()).slice(0,200))})\""
```
