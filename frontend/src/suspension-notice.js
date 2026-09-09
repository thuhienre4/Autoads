const rules = [
  ['circumventing', 'Né tránh hệ thống', ['circumventing systems', 'né tránh hệ thống', 'tránh né hệ thống'], 'Đối chiếu chính sách Né tránh hệ thống với website và cách quản lý tài khoản; ghi lại các thay đổi đã thực hiện trước khi kháng nghị.'],
  ['payments', 'Hoạt động thanh toán đáng ngờ', ['suspicious payment', 'thanh toán đáng ngờ'], 'Kiểm tra hồ sơ thanh toán và hoàn tất yêu cầu xác minh phương thức thanh toán nếu Google yêu cầu.'],
  ['balance', 'Số dư chưa thanh toán', ['unpaid balance', 'số dư chưa thanh toán'], 'Kiểm tra khoản còn nợ trong phần Thanh toán và làm theo thông báo của Google.'],
  ['verification', 'Xác minh nhà quảng cáo', ['advertiser verification', 'xác minh nhà quảng cáo'], 'Mở phần Xác minh nhà quảng cáo, xem nhiệm vụ và hạn hoàn tất. Việc nhắc đến xác minh chưa đủ xác nhận nguyên nhân tạm ngưng.'],
  ['business', 'Hoạt động kinh doanh không được chấp nhận', ['unacceptable business practices', 'hoạt động kinh doanh không được chấp nhận'], 'Đối chiếu nội dung website, thông tin doanh nghiệp và ưu đãi với chính sách được nêu trong thông báo.'],
  ['misrepresentation', 'Trình bày sai', ['misrepresentation', 'trình bày sai'], 'Kiểm tra tính chính xác của thông tin doanh nghiệp, giá và các cam kết trên quảng cáo và trang đích.'],
];

export function analyzeNotice(text) {
  const normalized = String(text || '').normalize('NFC').toLocaleLowerCase('vi');
  return rules.flatMap(([code, label, phrases, action]) => {
    const evidence = phrases.find(phrase => normalized.includes(phrase));
    return evidence ? [{ code, label, evidence, action }] : [];
  });
}
