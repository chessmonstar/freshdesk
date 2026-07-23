"""BM25 retrieval over the bundled Q&A index (built by build_index.py)."""
import gzip, json, math, re, collections

STOP = set(
    "the a an and or to of is are was were be been for on in at it this that with my your "
    "our we you i he she they them me us as if so but not no yes do does did have has had "
    "will would can could should there here what when how why who which you're im i'm "
    "please thanks thank hi hello hey ok okay just get got".split()
)


def toks(s):
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower())
            if len(t) > 1 and t not in STOP]


class Index:
    def __init__(self, path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            self.docs = json.load(f)
        self.doc_toks = [toks(d["q"]) for d in self.docs]
        self.N = len(self.docs)
        self.avgdl = max(1.0, sum(len(t) for t in self.doc_toks) / self.N)
        df = collections.Counter()
        for t in self.doc_toks:
            for w in set(t):
                df[w] += 1
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for w, n in df.items()}
        self.tf = [collections.Counter(t) for t in self.doc_toks]
        self.k1, self.b = 1.5, 0.75

    def search(self, query, k=5, exclude_tid=None):
        qset = set(toks(query))
        if not qset:
            return []
        scores = []
        for i, d in enumerate(self.docs):
            if exclude_tid and d["tid"] == exclude_tid:
                continue
            tf = self.tf[i]; dl = len(self.doc_toks[i]); s = 0.0
            for w in qset:
                f = tf.get(w)
                if f:
                    s += self.idf.get(w, 0) * (f * (self.k1 + 1)) / (
                        f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [dict(self.docs[i], score=round(sc, 2)) for sc, i in scores[:k]]


_INDEX = None


def get_index(path):
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(path)
    return _INDEX
