def create_analysis_output(
    analysis_type,
    evidence_id,
    status,
    result=None,
    message=None
):

    return {
        "status": status,
        "analysis_type": analysis_type,
        "evidence_id": evidence_id,
        "result": result,
        "message": message
    }