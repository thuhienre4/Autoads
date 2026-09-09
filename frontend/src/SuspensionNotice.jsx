import React from 'react';
import { analyzeNotice } from './suspension-notice.js';

export default function SuspensionNotice({ customerId }) {
  const storageKey = `ads-suspension-notice:${customerId}`;
  const [text, setText] = React.useState(() => {
    try { return localStorage.getItem(storageKey) || ''; } catch { return ''; }
  });
  const [message, setMessage] = React.useState('');
  const matches = analyzeNotice(text);
  const save = () => {
    try {
      if (text.trim()) localStorage.setItem(storageKey, text);
      else localStorage.removeItem(storageKey);
      setMessage('Đã lưu trên trình duyệt này.');
    } catch { setMessage('Không lưu được trên trình duyệt này. Bạn vẫn có thể đọc kết quả bên dưới.'); }
  };
  return <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
    <h3 className="font-bold">Đọc lý do trong thông báo Google · {customerId}</h3>
    <p className="mt-1 text-slate-600">Dán nguyên văn cảnh báo hoặc email của đúng tài khoản. Nội dung chỉ được lưu trên trình duyệt này khi bấm Lưu.</p>
    <textarea aria-label="Thông báo tạm ngưng của Google" maxLength={12000} value={text} onChange={event => { setText(event.target.value); setMessage(''); }} placeholder="Ví dụ: Your account is suspended due to suspicious payment activity." className="mt-2 min-h-28 w-full rounded-lg border border-slate-300 bg-white p-3" />
    <div className="flex flex-wrap gap-2">
      <button type="button" onClick={save} className="rounded-lg bg-blue-600 px-3 py-2 font-bold text-white">Lưu thông báo</button>
      <button type="button" onClick={() => { setText(''); try { localStorage.removeItem(storageKey); setMessage('Đã xóa thông báo đã lưu.'); } catch { setMessage('Không xóa được bản lưu trong trình duyệt.'); } }} className="rounded-lg border border-slate-300 bg-white px-3 py-2">Xóa</button>
    </div>
    {message && <p role="status" className="mt-2">{message}</p>}
    {text.trim() && <div className="mt-3 space-y-2">
      <p className="font-bold">Nhóm vấn đề được nhắc đến trong thông báo</p>
      <p className="text-xs text-slate-600">Nhận diện theo cụm từ, chưa xác nhận nguyên nhân tạm ngưng. Nội dung phủ định hoặc email liệt kê nhiều chính sách cần được đối chiếu thủ công.</p>
      {matches.length ? matches.map(match => <div key={match.code} className="rounded-lg border border-amber-200 bg-white p-3"><strong>{match.label}</strong><p>Cụm từ nhận diện: “{match.evidence}”</p><p className="mt-1">{match.action}</p></div>) : <p>Chưa nhận diện được lý do cụ thể. Hãy xem nguyên văn thông báo trong Google Ads; trạng thái SUSPENDED không đủ để suy ra lỗi.</p>}
      <a href="https://support.google.com/google-ads/answer/9841640?hl=vi" target="_blank" rel="noreferrer" className="inline-block font-bold text-blue-700 underline">Hướng dẫn tạm ngưng và kháng nghị của Google</a>
    </div>}
  </div>;
}
