# Writing posts

Posts are Markdown notes written in Obsidian. `python build.py` turns them into pages under `blog/`.

## One-time setup

1. Install [Pandoc](https://pandoc.org/installing.html) (on Windows: `winget install --id JohnMacFarlane.Pandoc`) and Python 3. Check with `pandoc --version` and `python --version`.
2. In `build.py`, set `SITE` to your address, for example `https://yourname.github.io`.
3. In Obsidian choose *Open folder as vault* and pick the `posts` folder.
4. In Obsidian, Settings, Files and links:
   - turn off *Use [[Wikilinks]]*
   - set *New link format* to *Relative path to file*
   - set *Default location for new attachments* to *Same folder as current file*

## Writing

Each post is a folder with one note in it, named the same as the folder, which becomes the address:

    posts/my-post/my-post.md   ->   blog/my-post/index.html

`python build.py new my-post "My title"` creates the folder and note. Start the note with:

    ---
    title: My title
    date: 2026-10-26
    description: One sentence for link previews and the feed.
    ---

Optional fields: `updated: 2026-11-02`, `draft: true` (not built), and `css: [extra.css]` for a stylesheet that sits beside the note. Put quotes round a title that contains a colon.

- Use `##` for sections. The title comes from the front matter.
- Paste or drag images into the note. Write what the image shows as its alt text: `![alt text](fig.svg)`. Add `{.wide}` after it to let a figure run wider than the text, and `"caption"` inside the brackets for a visible caption.
- Maths is `$x$` inline and `$$ ... $$` as a block. Tables are ordinary Markdown tables.
- Save charts as SVG (`plt.savefig("fig.svg")`, or `fig.write_image("fig.svg")` in Plotly). SVG stays sharp and needs no JavaScript.
- Raw HTML passes straight through, so a post can break the site's rules when it needs to. For an interactive Plotly chart, save `fig.write_html("chart.html", include_plotlyjs="cdn")` beside the note and add `<iframe src="chart.html" title="What the chart shows" height="540" loading="lazy"></iframe>`. Obsidian may not preview it.

Obsidian syntax that is converted: `%% comments %%` are dropped, `==highlight==` becomes `<mark>`, `![[image.png]]` and `![alt|300](image.png)` become images, `[[links]]` become plain text, and `--` becomes an em dash. Callouts, note embeds and plugins such as Dataview are not supported.

## Publishing

1. Run `python build.py`. It writes the post pages and copies their images, then rebuilds the post list on the blog page, the list on the home page, and `feed.xml`. It warns about any image it cannot find.
2. Open `blog/my-post/index.html` in a browser to check it.
3. Commit and push.

Edit the note, not the generated `blog/my-post/index.html`, which is overwritten on every build.

Everything in the repository is public once pushed, including `posts/` and drafts. To keep drafts private, move the vault outside the repository and set `POSTS` in `build.py` to its full path.
