from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120
MIN_CHUNK_LENGTH = 20
@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    source_location:str
def create_text_splitter(
        chunk_size :int=DEFAULT_CHUNK_SIZE,
        chunk_overlap:int =DEFAULT_CHUNK_OVERLAP,
)  -> RecursiveCharacterTextSplitter:
     return RecursiveCharacterTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      separators=[
          "\n# ",
          "\n## ",
          "\n### ",
          "\n#### ",
          "\n\n",
          "\n",
          " ",
          "",
      ],
      keep_separator=True,
      add_start_index=True,
  )
def chunk_text(
      text: str,
      chunk_size: int = DEFAULT_CHUNK_SIZE,
      chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
      min_chunk_length: int = MIN_CHUNK_LENGTH,
  ) -> list[TextChunk]:
     splitter =create_text_splitter( chunk_size=chunk_size,
          chunk_overlap=chunk_overlap,
          )
     documents = splitter.create_documents([text])
     chunks: list[TextChunk]=[]

     for document in documents:
          content = document.page_content.strip()

          if len(content) < min_chunk_length:
               continue

          start_index = document.metadata.get("start_index")
          if not isinstance(start_index,int):
               start_index = text.find(document.page_content)

          if start_index < 0:
               start_index = 0

          end_index = start_index +len(document.page_content)
           
          chunks.append(
               TextChunk(
                    chunk_index=len(chunks),
                    content=content,
                    source_location=f"chars:{start_index}-{end_index}",
               )
          )
     return chunks

     

    
