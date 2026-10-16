from langchain_text_splitters import RecursiveCharacterTextSplitter


class RecursiveTextChunker:
    def __init__(self, chunk_size_chars: int, chunk_overlap_chars: int) -> None:
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size_chars, chunk_overlap=chunk_overlap_chars)

    def split(self, text: str) -> list[str]:
        return self.splitter.split_text(text)
