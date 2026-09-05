import React from "react";
import { reviewPolicy } from "./policy-review.js";

export default function PolicyReview({ generated, landingPageUrl }) {
  const report = reviewPolicy(generated || {}, landingPageUrl);
  return (
    <section className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4" aria-label="Kiểm tra chính sách Google Ads">
      <h3 className="text-base font-bold text-slate-950">Kiểm tra nội dung Google Ads</h3>
      <p className="mt-1 text-sm text-slate-700">{report.findings.length ? `${report.findings.length} điểm cần xem lại` : "Chưa phát hiện dấu hiệu trong các quy tắc đã kiểm tra"} · {report.checkedAssets} mẫu nội dung. Tự cập nhật khi bạn sửa.</p>
      <p className="mt-2 text-xs leading-5 text-slate-600">Cảnh báo tham khảo bằng quy tắc tiếng Việt/Anh, không phải kết luận vi phạm hay bảo đảm được Google duyệt. Chưa kiểm tra đầy đủ ngành hàng, quốc gia, hình ảnh và tài khoản.</p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{report.pageReviewed ? "Đã rà bản trích landing page từ lần tạo nội dung gần nhất; chưa kiểm tra toàn bộ website hoặc xác thực ưu đãi." : "Chưa rà được nội dung landing page. Hãy phân tích trang và kiểm tra trực tiếp khả năng truy cập, giá, ưu đãi và thông tin doanh nghiệp."}</p>
      <div className="mt-3 space-y-3">
        {report.findings.map((item) => (
          <div key={item.id} className="rounded-lg border border-amber-200 bg-white p-3 text-sm">
            <p className="font-bold text-amber-900">{item.field}: {item.title}</p>
            <p className="mt-1 break-words text-slate-800">“{item.evidence}”</p>
            <p className="mt-1 text-slate-600">{item.fix}</p>
            <a href={item.url} target="_blank" rel="noreferrer" className="mt-2 inline-block font-semibold text-blue-700 underline">Chính sách Google liên quan</a>
          </div>
        ))}
      </div>
    </section>
  );
}
