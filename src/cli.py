import argparse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="font", description="手写字库补全流水线")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, doc, **kw):
        sp = sub.add_parser(name, help=doc)
        for flag, opts in kw.items():
            sp.add_argument(*opts["args"], **opts["kwargs"])
        return sp

    add("init", "初始化数据库与 GB2312 一级队列")
    add("status", "查看队列状态")
    add("stdsrc", "渲染标准字形作为配对内容源", src=dict(args=["--src"], kwargs={"default": "msh"}))
    add("import", "盘点 assets 素材，生成清单")
    add("preprocess", "预处理素材成 256 网格")
    add("classify", "备选图归类打标")
    add("anchors", "风格聚类与锚点挑选")
    add("components", "构建部件库与拆分表")
    add("build_parts", "从手写整字裁出部件真件，建部件库")
    add("assemble", "用部件真件按标准字形拼装缺字")
    add("train", "训练 Pix2Pix 风格迁移", epochs=dict(args=["--epochs"], kwargs={"type": int, "default": 80}), batch=dict(args=["--batch"], kwargs={"type": int, "default": 16}))
    add("generate", "生成缺字候选", charset=dict(args=["--charset"], kwargs={"default": "level1"}))
    add("qa", "自动质检打分")
    add("rework", "自动返工")
    add("export", "导出字体文件", fmt=dict(args=["--fmt"], kwargs={"default": "ttf"}))
    sp = add(
        "review",
        "启动评审 WebUI",
        host=dict(args=["--host"], kwargs={"default": None}),
        port=dict(args=["--port"], kwargs={"type": int, "default": None}),
        config=dict(args=["--config"], kwargs={"default": None}),
    )

    return p


def main() -> None:
    args = build_parser().parse_args()
    cmd = args.command

    if cmd == "init":
        from .stage_init import ensure_db

        ensure_db()
    elif cmd == "import":
        from .stage_import import run_import

        run_import()
    elif cmd == "status":
        from .stage_status import run

        run()
    elif cmd == "stdsrc":
        from .stage_stdsrc import run

        run()
    elif cmd == "review":
        from .stage_review import run

        run(host=args.host, port=args.port, config=args.config)
    elif cmd == "preprocess":
        from .stage_preprocess import run

        run()
    elif cmd == "classify":
        from .stage_classify import run

        run()
    elif cmd == "anchors":
        from .stage_anchors import run

        run()
    elif cmd == "components":
        from .stage_components import run

        run()
    elif cmd == "build_parts":
        from .stage_parts import build

        build()
    elif cmd == "assemble":
        from .stage_assemble import run

        run()
    elif cmd == "train":
        from .stage_train import run

        run(epochs=args.epochs, batch=args.batch)
    elif cmd == "generate":
        from .stage_generate import run

        run()
    elif cmd == "qa":
        from .stage_qa import run

        run()
    elif cmd == "rework":
        from .stage_rework import run

        run()
    elif cmd == "export":
        from .stage_export import run

        run(fmt=args.fmt)


if __name__ == "__main__":
    main()