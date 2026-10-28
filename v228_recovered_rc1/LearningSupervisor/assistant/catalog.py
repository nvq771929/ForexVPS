"""Grounded facts and research questions; model prose never enters the report."""

QUESTIONS = {
    'Q_VALIDATE_CONTEXT': 'Đối chiếu bối cảnh trên giai đoạn mới trước khi đề xuất lọc Entry.',
    'Q_CHECK_AGE': 'Kiểm tra phân phối thời gian duy trì sau xác nhận; chưa coi tuổi quan sát là vị trí trong chu kỳ.',
    'Q_CHECK_DATA': 'Kiểm tra khoảng thiếu dữ liệu và nguồn nến; giữ UNKNOWN khi chưa đủ bằng chứng.',
    'Q_CHECK_ENTRY': 'Đối chiếu riêng LOSS tránh được và WIN bỏ nhầm ở kỳ hạn 30 phút.',
}

def facts_for(snapshot, native, progress):
    def fact(identity, text, evidence):
        return dict(id=identity, text=text, evidence=evidence)
    result = [fact('CAPABILITY',
        'Trợ lý chỉ quan sát. Chưa có mô hình 30 phút đủ kiểm định; không chấm xác suất WIN hoặc thay tín hiệu EA.',
        dict(contract='V224_LOCAL_EXPLANATION_ASSISTANT_V1', ea_effects=False, probability=None))]
    if snapshot is None:
        result.append(fact('CONTEXT', 'Chưa có bối cảnh RC1: thiếu nến hoặc chưa xác nhận múi giờ nguồn.',
                           dict(ready=False, clock_known=progress['clock_known'])))
    else:
        result.append(fact('CONTEXT',
            f"Bối cảnh RC1: {snapshot['direction']}; trạng thái {snapshot['phase']}. Đây là mô tả theo quy tắc, chưa phải dự báo thắng lệnh.",
            {k:snapshot[k] for k in ('asof_ms','direction','phase','ready')}))
        age = snapshot['observed_age_minutes']
        result.append(fact('AGE',
            'Chưa có tuổi xu hướng đã xác nhận.' if age is None else
            f'Tuổi từ lúc công cụ xác nhận: {age:g} phút; chưa xác định được phần trăm chu kỳ hay thời điểm kết thúc.',
            dict(observed_age_minutes=age, detected_start_ms=snapshot['detected_start_ms'])))
        result.append(fact('VOLATILITY', f"Độ biến động: {snapshot['volatility']}; tách biệt với hướng xu hướng.",
            dict(volatility=snapshot['volatility'],ratio=snapshot['volatility_ratio'])))
        if snapshot['phase_flags']:
            result.append(fact('PHASE_FLAGS',
                'Cờ sức khỏe của bối cảnh: '+', '.join(snapshot['phase_flags'])+'. Không tự coi đây là tín hiệu EA yếu hoặc điều kiện veto.',
                dict(flags=snapshot['phase_flags'])))
    if native:
        action = {1:'CALL',-1:'PUT',0:'WAIT'}[native['action']]
        label = 'Quyết định tại LOCK' if native['kind']==3 else 'Ứng viên tại ANCHOR, chưa phải tín hiệu đã phát'
        result.append(fact('NATIVE', f"{label}: {action}; reason={native['reason']}; kỳ hạn native {native['horizon_minutes']} phút.", native))
    result.append(fact('WARMUP',
        f"Đã đọc {progress['closed_m5_used']} nến M5; H1 hoàn chỉnh {progress['completed_h1']}/150 cần cho khởi tạo. Tăng số nến chưa đồng nghĩa chất lượng dự báo tăng.",
        {k:progress[k] for k in ('closed_m5_used','completed_h1','completed_m15','clock_known')}))
    if progress['late_bars_ignored']:
        result.append(fact('LATE_DATA',
            f"{progress['late_bars_ignored']} nến xuất hiện muộn được ghi riêng; không quay lại sửa bối cảnh đã ghi.",
            dict(late_bars_ignored=progress['late_bars_ignored'])))
    return result

def validate_selection(value, facts):
    if not isinstance(value,dict) or set(value)!= {'fact_ids','question_ids'}:
        raise ValueError('Local model selection schema differs')
    allowed={r['id'] for r in facts}
    for key, maximum, permitted in [('fact_ids',6,allowed),('question_ids',2,set(QUESTIONS))]:
        items=value[key]
        if not isinstance(items,list) or not 1<=len(items)<=maximum or any(not isinstance(x,str) or x not in permitted for x in items) or len(set(items))!=len(items):
            raise ValueError('Local model selected unknown/duplicate evidence')
    return value

def default_selection(facts):
    ids=[r['id'] for r in facts]
    return dict(fact_ids=ids[:6],question_ids=['Q_VALIDATE_CONTEXT','Q_CHECK_ENTRY'])
