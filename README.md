# React Aria Agent Skill mirror

An **unofficial, automatically updated mirror** of the official React Aria Agent Skill published by Adobe. This repository is not affiliated with or endorsed by Adobe.

The files under [`skills/react-aria/`](skills/react-aria/) come from Adobe's published skill archive, without editorial changes. The updater and workflows are maintained here, separately from the mirrored content.

## Import into Replit

After the setup pull request has been merged:

1. Open **Workspace Settings → Customization → Skills**.
2. Choose **Add → GitHub** and paste:

   ```text
   https://github.com/AURVEXI/react-aria-skill/tree/main/skills/react-aria
   ```

3. Preview and import the `react-aria` skill. If an older skill with that name is already installed, use the workspace's replacement/update controls rather than leaving two copies enabled.

This repository stays current with Adobe. Updating an already-imported Replit workspace copy is a separate operation: use the GitHub skill's update/sync control when available. This mirror does not modify your Replit workspace itself.

For CLI-based skill installers:

```sh
npx skills add https://github.com/AURVEXI/react-aria-skill --skill react-aria
```

## How synchronization works

- GitHub Actions checks daily at **06:17 UTC** (GitHub may delay scheduled runs).
- To check immediately, open **Actions → Sync Adobe React Aria skill → Run workflow** on the default branch.
- The updater downloads Adobe's discovery index and the archive it advertises, verifies the advertised SHA-256 digest, and validates every archive entry before replacing the skill directory.
- Archive links, path traversal, duplicate files, unexpected top-level files, oversized downloads, and invalid skill metadata fail closed.
- The workflow never executes code from the downloaded bundle.
- Changes are committed directly to the default branch, limited to `skills/react-aria/` and `upstream.json`. No commit is made when these files are unchanged.
- The workflow uses GitHub's built-in, repository-scoped token. **No personal access token or repository secret is needed.**
- `upstream.json` records the verified archive digest and individual file digests. Digest verification detects corruption; it is not an independent signature because Adobe serves both the index and the archive.

GitHub may disable scheduled workflows in public repositories after 60 days without repository activity. If this happens, re-enable the workflow in **Actions**. A branch rule that blocks direct bot pushes will also block automatic updates; this setup does not bypass branch protection.

## Upstream and license

- [Adobe's official installation instructions](https://react-aria.adobe.com/ai)
- [Official discovery index](https://react-aria.adobe.com/.well-known/agent-skills/index.json)
- [Adobe's skill generator source](https://github.com/adobe/react-spectrum/blob/main/packages/dev/s2-docs/scripts/generateAgentSkills.mjs)
- [Adobe React Spectrum repository](https://github.com/adobe/react-spectrum)

Adobe's skill and references are Apache-2.0 licensed. See [LICENSE](LICENSE), retained upstream notices, and [NOTICE](NOTICE). The mirror's automation is also provided under Apache-2.0.

## Local checks

Python 3.10+ is sufficient; there are no third-party dependencies.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/sync_skill.py
git diff --stat
```

Tests use in-memory fixtures and do not access the network. Running the sync command contacts Adobe and updates the mirrored files and provenance manifest.
