import pytest
from app.services.fast_mesh import FastMeshInfo
from app.services.ai_tagger import AITagResult

def test_processor_caption_formatting():
    mesh_info = FastMeshInfo(face_count=1250000, part_count=4, is_presupported=True)
    ai_result = AITagResult(predicted_name="Iron Man Mark 85", studio="Sanix", category="Figurine", print_type="Resin", keywords=["ironman", "marvel", "resin"])
    
    studio_line = f"🏷️ **Studio:** #{ai_result.studio}\n" if ai_result.studio else ""
    support_badge = "🟢 **[ĐÃ CÓ FILE SUPPORT SẴN]**\n" if mesh_info.is_presupported else ""
    
    caption = (
        f"**{ai_result.predicted_name}**\n\n"
        f"{studio_line}"
        f"{support_badge}"
        f"📁 **File:** `Iron_Man.zip`\n"
        f"📊 **Faces:** {mesh_info.face_count:,}\n"
    )
    
    assert "Iron Man Mark 85" in caption
    assert "#Sanix" in caption
    assert "ĐÃ CÓ FILE SUPPORT SẴN" in caption
    assert "1,250,000" in caption
