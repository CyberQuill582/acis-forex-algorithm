# GCP runbook — Dukascopy OOS tick download (ACIS §14 guard-2)

Downloads the ratified 8-instrument, 14-yr (2012–2025) tick set on a Google Cloud VM.
Script: [`download_dukascopy.js`](download_dukascopy.js). Everything below is copy-paste.

> **Cost:** runs on a small VM for ~1–2 days, a few dollars of the **$300 / 90-day free
> credit** — nowhere near the cap. **Delete the VM when the download is done** (step 6) so
> it stops billing. The 30 GB Always-Free disk is too small for the ~35 GB output, so this
> uses the credit, not the free tier.

---

## 1. Create the VM (Cloud Console — easiest)

Console → **Compute Engine → VM instances → Create instance**:
- **Name:** `acis-dl`
- **Region:** `us-central1` (any is fine)
- **Machine type:** `e2-small` (2 GB RAM — enough for monthly chunks)
- **Boot disk:** click **Change** → Ubuntu 24.04 LTS → **size 80 GB** (default 10 GB is too small)
- Leave everything else default → **Create**

When it's up, click **SSH** next to the instance — a browser terminal opens. Run the rest there.

## 2. Install Node + tmux

```bash
sudo apt update && sudo apt install -y tmux
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # expect v20.x
```

## 3. Get the downloader onto the VM

You only need the two files in `scripts/`. Easiest is to paste them:

```bash
mkdir -p ~/acis-dl && cd ~/acis-dl
nano download_dukascopy.js     # paste the file's contents, Ctrl-O, Enter, Ctrl-X
nano package.json              # paste the file's contents, Ctrl-O, Enter, Ctrl-X
npm install                    # installs dukascopy-node
```

*(Or, if this repo is on a git host you can reach: `git clone <url>` and `cd acis/scripts`.)*

## 4. Run it so it survives disconnects

```bash
cd ~/acis-dl
tmux new -s dl
node download_dukascopy.js 2>&1 | tee -a run.log
```
Detach and let it run unattended: **Ctrl-B** then **D**. You can now close the browser tab —
the download keeps going on the VM.

## 5. Monitor

Reconnect any time (SSH → then `tmux attach -t dl`), or check without attaching:

```bash
tail -f ~/acis-dl/download.log                    # live, timestamped progress
ls ~/acis-dl/data/dukascopy/*/*.gz | wc -l        # chunks done   (target: 1344)
du -sh ~/acis-dl/data/dukascopy/*                 # size per instrument
grep -c FAIL ~/acis-dl/download.log               # any failures?
df -h /                                            # disk headroom
```

**Target = 1344 chunks** (8 instruments × 14 years × 12 months). Expected total ~35 GB
gzipped. A failed month is logged and skipped, never fatal — when the run finishes,
**just re-run `node download_dukascopy.js`** and it retries only what's missing (resume is
automatic; completed chunks are skipped).

## 6. Retrieve the data, then delete the VM

Pull the data down (run this on **your own machine**, needs `gcloud` installed & `gcloud auth login`):

```bash
gcloud compute scp --recurse acis-dl:~/acis-dl/data ./ --zone=us-central1-a
```

Then **delete the VM to stop billing**:
```bash
gcloud compute instances delete acis-dl --zone=us-central1-a
```
(or Console → VM instances → ⋮ → Delete.)

Land the `data/` tree at the repo root (`acis/data/dukascopy/...`) — that's where the
Dukascopy `TickSource` adapter will read it for the §14 grade.

---

### Rate-limit survival (already baked into the script)

| dukascopy-node option | default | this script | why |
|---|---|---|---|
| `retryCount` | **0** | **8** | default 0 loses a chunk on any transient error — the critical fix |
| `batchSize` | 10 | 5 | fewer concurrent requests → less throttling |
| `pauseBetweenBatchesMs` | 1000 | 3000 | docs: for large downloads minimise batch, maximise pause |
| `pauseBetweenRetriesMs` | 500 | 3000 | back off properly between retries |

Monthly chunking keeps peak RAM ~150 MB (safe on a 2 GB VM) and makes the whole run
resumable at month granularity.
