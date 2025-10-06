from src.shared.cache import (
    redis_key_for_files_list,
    redis_key_for_file_detail,
    redis_key_for_emb_pages,
    redis_key_for_emb_search_file,
    redis_key_for_emb_search_tenant,
)


def test_cache_key_shapes():
    assert redis_key_for_files_list("tid") == "files:list:tid"
    assert redis_key_for_file_detail("tid", "fid") == "files:detail:tid:fid"
    assert redis_key_for_emb_pages("fid") == "emb:pages:fid"
    assert redis_key_for_emb_search_file("fid", "h", 5) == "emb:search:f:fid:h:5"
    assert redis_key_for_emb_search_tenant("tid", "h", 5) == "emb:search:t:tid:h:5"

