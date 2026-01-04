import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pipeline import run_pipeline
from storage import load_json, save_json


class NewsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("뉴스 미니프로젝트")

        self.dataset = None
        self.fetch_thread = None
        self.queue = queue.Queue()

        self.query_var = tk.StringVar()
        self.count_var = tk.IntVar(value=5)
        self.lang_var = tk.StringVar(value="en")

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")

        ttk.Label(top, text="검색어").pack(side="left")
        ttk.Entry(top, textvariable=self.query_var, width=30).pack(side="left", padx=4)

        ttk.Label(top, text="개수").pack(side="left")
        ttk.Spinbox(top, from_=1, to=100, textvariable=self.count_var, width=5).pack(side="left", padx=4)

        ttk.Label(top, text="언어").pack(side="left")
        lang_combo = ttk.Combobox(
            top,
            textvariable=self.lang_var,
            values=["en", "ko", "ja", "fr", "de", "es"],
            width=5,
            state="readonly",
        )
        lang_combo.pack(side="left", padx=4)

        ttk.Button(top, text="가져오기", command=self.on_fetch).pack(side="left", padx=4)
        ttk.Button(top, text="JSON 저장", command=self.on_save).pack(side="left", padx=4)
        ttk.Button(top, text="JSON 불러오기", command=self.on_load).pack(side="left", padx=4)

        body = ttk.Frame(self.root, padding=6)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y")

        self.listbox = tk.Listbox(left, width=50)
        self.listbox.pack(side="left", fill="y", expand=False)
        list_scroll = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        list_scroll.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=list_scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.detail_text = tk.Text(right, wrap="word")
        self.detail_text.pack(side="left", fill="both", expand=True)
        detail_scroll = ttk.Scrollbar(right, orient="vertical", command=self.detail_text.yview)
        detail_scroll.pack(side="left", fill="y")
        self.detail_text.config(yscrollcommand=detail_scroll.set)

    def on_fetch(self):
        query = self.query_var.get().strip()
        if not query:
            messagebox.showerror("오류", "검색어를 입력하세요.")
            return

        if self.fetch_thread and self.fetch_thread.is_alive():
            messagebox.showinfo("안내", "이미 가져오는 중입니다.")
            return

        try:
            count = int(self.count_var.get())
        except ValueError:
            messagebox.showerror("오류", "개수 값이 올바르지 않습니다.")
            return

        language = self.lang_var.get().strip() or "en"

        self.fetch_thread = threading.Thread(
            target=self._fetch_worker, args=(query, count, language), daemon=True
        )
        self.fetch_thread.start()
        self.root.after(100, self._check_queue)

    def _fetch_worker(self, query: str, count: int, language: str):
        try:
            dataset = run_pipeline(query, count, language)
            if not dataset["articles"]:
                raise ValueError("검색 결과가 없습니다.")
            self.queue.put(("ok", dataset))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _check_queue(self):
        try:
            kind, payload = self.queue.get_nowait()
        except queue.Empty:
            if self.fetch_thread and self.fetch_thread.is_alive():
                self.root.after(100, self._check_queue)
            return

        if kind == "ok":
            self.dataset = payload
            self.refresh_list()
        else:
            messagebox.showerror("오류", payload)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        self.detail_text.delete("1.0", tk.END)

        if not self.dataset:
            return

        label_map = {"positive": "POS", "neutral": "NEU", "negative": "NEG"}
        for article in self.dataset.get("articles", []):
            sentiment = article.get("sentiment", {})
            label = label_map.get(sentiment.get("label"), "UNK")
            source = article.get("source") or "알 수 없음"
            title = article.get("title") or "(제목 없음)"
            self.listbox.insert(tk.END, f"[{label}] {source} - {title}")

    def on_select(self, _event):
        if not self.dataset:
            return

        selection = self.listbox.curselection()
        if not selection:
            return

        article = self.dataset["articles"][selection[0]]
        sentiment = article.get("sentiment", {})
        detail = (
            f"제목: {article.get('title', '')}\n"
            f"출처: {article.get('source', '')}\n"
            f"날짜: {article.get('publishedAt', '')}\n"
            f"URL: {article.get('url', '')}\n"
            f"감성: {sentiment.get('label', '')} ({sentiment.get('score', 0.0):.2f})\n\n"
            f"요약:\n{article.get('summary', '')}\n\n"
            f"본문:\n{article.get('text', '')}\n"
        )

        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, detail)

    def on_save(self):
        if not self.dataset:
            messagebox.showerror("오류", "저장할 데이터가 없습니다.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return

        try:
            save_json(self.dataset, path)
        except Exception as exc:
            messagebox.showerror("오류", str(exc))

    def on_load(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return

        try:
            data = load_json(path)
            if "articles" not in data:
                raise ValueError("JSON 스키마가 올바르지 않습니다.")
            self.dataset = data
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("오류", str(exc))


def main():
    root = tk.Tk()
    app = NewsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
