import os
from fabric import Connection
from pathlib import Path
import sys
sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

print("Installing pyglet<2...")
c.run("docker exec stl_api pip install 'pyglet<2' --force-reinstall", hide=True)
c.run("docker exec stl_worker pip install 'pyglet<2' --force-reinstall", hide=True)

script = """
import os
import sys
import numpy as np

# Set EGL
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
import pyrender

scene = pyrender.Scene(bg_color=[0.12, 0.12, 0.12, 1.0])
renderer = pyrender.OffscreenRenderer(512, 512)
color, depth = renderer.render(scene)
print("Rendered! Shape:", color.shape)
"""

c.run("cat << 'EOF' > /root/test_render.py\n" + script + "\nEOF")
c.run("docker cp /root/test_render.py stl_api:/tmp/test_render.py", hide=True)
print("Running test inside stl_api...")
res = c.run("docker exec stl_api python /tmp/test_render.py", hide=True, warn=True)
print(res.stdout)
print(res.stderr)
os.unlink(pem)
