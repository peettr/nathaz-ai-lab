import subprocess, sys, pathlib
root=pathlib.Path(sys.argv[1]); out=root/'out.html'
subprocess.run([str(root/'node_modules/.bin/esbuild'), str(root/'src/main.js'),'--bundle','--minify','--format=iife','--target=es2020',f'--outfile={root}/bundle.js'],check=True,cwd=root)
js=(root/'bundle.js').read_text(); assert '</script>' not in js.lower()
tpl=(root/'template.html').read_text()
data='window.__UR5E='+(root/'ur5e_packed.json').read_text()+';'
out.write_text(tpl.replace('__DATA__',data).replace('__BUNDLE__',js),encoding='utf-8'); print(out.stat().st_size)
