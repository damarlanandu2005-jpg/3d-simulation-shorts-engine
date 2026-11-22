# ONE-CELL LAUNCHER: pulls the latest kit + runner from GitHub and runs everything (setup, GPU check, benchmark/full render, results push).
# Colab: Runtime > Change runtime type > T4 GPU. Optional: add a Colab Secret named GITHUB_TOKEN (repo write) so results are pushed back.
import subprocess, shutil
BRANCH = "casino30-kit"
REPO = "damarlanandu2005-jpg/3d-simulation-shorts-engine"
shutil.rmtree("/content/repo", ignore_errors=True)
r = subprocess.run(["git", "clone", "--depth", "1", "-b", BRANCH, "https://github.com/%s" % REPO, "/content/repo"], capture_output=True, text=True)
print(r.stdout[-300:], r.stderr[-300:])
assert r.returncode == 0, "clone failed - is the repo public / branch name right?"
exec(open("/content/repo/casino30/colab/runner.py").read())
