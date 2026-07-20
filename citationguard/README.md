# CitationGuard Portfolio Page

这是一个独立的静态作品集页面，参考 `SSkeaido/meow` 的展示方式制作：首屏定位、产品洞察、解决方案、架构、评测和交付物都集中在一个长页面中。

## 本地预览

在仓库根目录运行：

```powershell
python -m http.server 4173 --directory portfolio
```

然后打开 <http://127.0.0.1:4173>。

## 部署到 GitHub Pages

可以把 `portfolio` 目录作为静态站点发布，或将其中的 `index.html` 和 `styles.css` 复制到单独的作品集仓库。页面没有依赖构建工具、图片服务或外部 CDN，适合 GitHub Pages、Cloudflare Pages 和任意静态托管。

页面中的项目文档链接默认指向当前仓库结构；如果单独部署，需要将这些链接替换成你的 GitHub 仓库地址。
