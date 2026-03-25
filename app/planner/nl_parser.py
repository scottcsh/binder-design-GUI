import re
from app.schemas.pipeline import BinderPipelineSpec


def _extract_target_pdb(text: str) -> str:
    m = re.search(r"(/[\w./-]+\.pdb|[\w./-]+\.pdb)", text)
    if not m:
        raise ValueError("Could not find target PDB path in the request")
    return m.group(1)


def _extract_hotspots(text: str) -> tuple[str, list[int]]:
    # 예: hotspot C:34,C:46,C:61,C:63,C:97
    m = re.search(r"(?:hotspot[s]?\s*)?([A-Za-z]):([\d,\s:]+)", text, re.IGNORECASE)
    if not m:
        return "C", []

    chain = m.group(1)
    nums = [int(x) for x in re.findall(r"\d+", m.group(2))]
    return chain, nums


def _extract_num_backbones(text: str) -> int:
    m = re.search(r"(\d+)\s*개", text)
    if m:
        return int(m.group(1))

    m = re.search(r"num_designs\s*=?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return 100


def _extract_contigs(text: str) -> str:
    # 사용자가 contigs=[...]를 직접 넣으면 그걸 우선 사용
    m = re.search(r"contigs\s*=?\s*(\[[^\]]+\])", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # 기본값: 1yjd 예제용
    return "[C1-118/0 60-80]"


def parse_nl_to_spec(text: str) -> BinderPipelineSpec:
    target_pdb = _extract_target_pdb(text)
    hotspot_chain, hotspot_residues = _extract_hotspots(text)
    num_backbones = _extract_num_backbones(text)
    contigs = _extract_contigs(text)

    return BinderPipelineSpec(
        workflow="binder_pipeline",
        target_pdb=target_pdb,
        contigs=contigs,
        num_backbones=num_backbones,
        hotspot_chain=hotspot_chain,
        hotspot_residues=hotspot_residues,
        noise_scale_ca=1.0,
        noise_scale_frame=1.0,
    )
