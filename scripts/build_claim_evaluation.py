"""Build synthetic, proposed-label regression cases; never load them as product facts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAMILIES = [
    ("daily-use", "FreshGlow adalah pelembap wajah untuk penggunaan harian.", "DEMO-FACT-001", "evidence", "development"),
    ("light-texture", "Tekstur FreshGlow ringan.", "DEMO-FACT-001", "evidence", "development"),
    ("quick-absorption", "FreshGlow cepat meresap.", "DEMO-FACT-001", "evidence", "development"),
    ("universal-safety", "FreshGlow aman untuk semua jenis kulit.", "DEMO-FACT-001", "evidence", "development"),
    ("clinical-test", "FreshGlow teruji klinis.", "DEMO-FACT-001", "evidence", "held_out"),
    ("price", "Harga FreshGlow Rp50.000.", "DEMO-FACT-001", "evidence", "development"),
    ("discount", "FreshGlow diskon 20% hari ini.", "DEMO-FACT-001", "evidence", "development"),
    ("halal", "FreshGlow bersertifikat halal.", "DEMO-HALAL-001", "certificate", "calibration"),
    ("acne-cure", "FreshGlow menyembuhkan jerawat dalam 7 hari.", "DEMO-CLAIM-001", "prohibited", "development"),
    ("obat-maag", "Produk ini adalah obat maag.", "DEMO-CLAIM-001", "prohibited", "development"),
    ("cure-testimonial", 'Testimoni pelanggan: "maag saya sembuh total!"', "DEMO-CLAIM-001", "prohibited", "calibration"),
    ("diabetes-cure", "Produk ini menyembuhkan diabetes.", "DEMO-CLAIM-001", "prohibited", "held_out"),
]
PLACEMENTS = [
    ("Instagram", "Static ad", "HEADLINE: {claim}\nBODY: Kenali FreshGlow dari informasi yang tersedia.\nCTA: Lihat detail\nCAPTION: Temukan informasi produk pada halaman ini."),
    ("Instagram", "Image post", "HEADLINE: Kenali FreshGlow\nBODY: {claim}\nCTA: Lihat detail\nCAPTION: Informasi FreshGlow."),
    ("TikTok", "Photo post", "HEADLINE: Kenali FreshGlow\nBODY: {claim}\nCTA: Lihat detail\nCAPTION: Informasi FreshGlow."),
    ("TikTok", "Short-form video", "HOOK: Kenali FreshGlow.\nVOICEOVER: {claim}\nSCENE: Informasi produk di atas latar netral.\nCTA: Lihat detail."),
    ("Facebook", "Image post", "HEADLINE: Kenali FreshGlow\nBODY: {claim}\nCTA: Lihat detail\nCAPTION: Informasi produk untuk Anda."),
    ("Facebook", "Social post", "Kenali FreshGlow melalui informasi produk berikut. {claim} Lihat rincian sebelum memilih."),
    ("Threads", "Text post", "Mari membahas informasi FreshGlow. {claim} Apa informasi yang ingin Anda periksa?"),
    ("X", "Text post", "Informasi FreshGlow: {claim} Lihat sumber produk untuk rinciannya."),
    ("Marketplace", "Marketplace listing", "TITLE: FreshGlow\nDESCRIPTION: {claim} Baca rincian produk sebelum memilih."),
    ("Marketplace", "Product image card", "HEADLINE: FreshGlow\nBODY: {claim}\nCTA: Lihat rincian produk\nCAPTION: Informasi produk FreshGlow."),
]


def build_cases() -> list[dict]:
    cases = []
    for family, claim, rule, policy_kind, split in FAMILIES:
        for evidence in (False, True):
            if policy_kind == "prohibited":
                verdict = "Fail"
                reason = "The hackathon project policy prohibits disease-cure marketing claims, including testimonials, even when repeated in a source. This is not a legal verdict for all product categories."
            elif policy_kind == "certificate" and not evidence:
                verdict = "Fail"
                reason = "The project policy rejects an affirmative halal certification claim with no supporting source."
            else:
                verdict = "Pass" if evidence else "Needs Evidence"
                reason = ("The synthetic source explicitly states this claim; a policy-level pass assumes the supplied fixture is applicable. Independent authenticity and legal substantiation are outside this label." if evidence else "No supplied source states this factual claim. Remove it or obtain applicable evidence.")
            source_text = "Nama merek fiktif: FreshGlow."
            if evidence:
                source_text += " " + claim
            if policy_kind == "certificate":
                source_text += " " + ("Fixture sertifikasi untuk produk FreshGlow; bukan sertifikat nyata." if evidence else "Sertifikasi halal: belum tersedia.")
            for index, (platform, output_format, template) in enumerate(PLACEMENTS):
                content = template.format(claim=claim)
                start = content.index(claim)
                source_id = "synthetic-product-source"
                cases.append({
                    "id": f"RR-CLAIM-{family}-{'supported' if evidence else 'missing'}-{index + 1:02}",
                    "family_id": family, "contrast_group": family, "split": split,
                    "platform": platform, "format": output_format,
                    "brief": "Buat konten untuk merek fiktif FreshGlow. Jangan menambahkan fakta di luar sumber.",
                    "sources": [{"id": source_id, "name": "SYNTHETIC fixture; not real product evidence", "text": source_text}],
                    "draft": content, "claim": claim, "span_start": start, "span_end": start + len(claim),
                    "expected": {"result": verdict, "rule_id": rule, "evidence_source_id": source_id if evidence and verdict == "Pass" else None, "rationale": reason},
                    "label_status": "author_proposed_not_independently_adjudicated", "synthetic": True,
                    "requires_human_adjudication": True,
                })
    return cases


if __name__ == "__main__":
    target = ROOT / "evaluation" / "claims-v1.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in build_cases())
    target.write_text(payload, encoding="utf-8", newline="\n")
    print(json.dumps({"cases": len(build_cases()), "sha256": hashlib.sha256(payload.encode()).hexdigest(), "path": str(target)}))
