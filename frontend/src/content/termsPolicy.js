export const TERMS_PRODUCT = "ContractLens";
export const TERMS_VERSION = "1.0";
export const TERMS_EFFECTIVE_DATE = "19/08/2026";
export const TERMS_TITLE = "Chính sách sử dụng dịch vụ và bảo vệ thông tin";

export const TERMS_INTRO = `Vui lòng đọc kỹ để hiểu cách ${TERMS_PRODUCT} xử lý thông tin của bạn, cách AI phân tích hợp đồng và những giới hạn khi dùng kết quả. Tiếp tục sử dụng dịch vụ nghĩa là bạn đã đọc và đồng ý với nội dung dưới đây.`;

/** The four points every user must know, shown first as cards. */
export const TERMS_HIGHLIGHTS = [
  {
    icon: "verified_user",
    tone: "quiet",
    title: "Dữ liệu dùng đúng mục đích",
    text: "Tài liệu và câu hỏi của bạn chỉ dùng để phân tích hợp đồng, nhận diện rủi ro và đưa ra khuyến nghị. Không dùng cho quảng cáo, tiếp thị hay xây dựng hồ sơ cá nhân.",
  },
  {
    icon: "shield_lock",
    tone: "ok",
    title: "Ẩn thông tin cá nhân",
    text: "Trước khi gửi cho AI, hệ thống ưu tiên ẩn hoặc thay thế thông tin cá nhân không cần thiết. Đây là biện pháp giảm thiểu, không bảo đảm loại bỏ hoàn toàn.",
  },
  {
    icon: "gavel",
    tone: "caution",
    title: "Không phải tư vấn pháp lý",
    text: "AI chỉ hỗ trợ phân tích và không thay thế luật sư hay chuyên gia pháp lý. Với việc quan trọng, hãy hỏi ý kiến chuyên gia.",
  },
  {
    icon: "fact_check",
    tone: "stamp",
    title: "Bạn kiểm tra và quyết định",
    text: "AI có thể sai hoặc bỏ sót. Hãy đối chiếu kết quả với hợp đồng và quy định hiện hành trước khi ký hoặc thực hiện.",
  },
];

export const TERMS_SECTIONS = [
  {
    id: "scope",
    icon: "dashboard",
    title: "Phạm vi dịch vụ",
    paragraphs: [
      `${TERMS_PRODUCT} cung cấp công cụ hỗ trợ phân tích và xem xét hợp đồng bằng trí tuệ nhân tạo. Tùy phiên bản, dịch vụ có thể gồm:`,
    ],
    bullets: [
      "Phân tích nội dung hợp đồng và giải thích các điều khoản.",
      "Nhận diện điều khoản có khả năng phát sinh rủi ro.",
      "Đề xuất điểm cần xem xét hoặc điều chỉnh.",
      "Trả lời câu hỏi liên quan đến nội dung hợp đồng.",
    ],
    after: ["Phạm vi và tính năng có thể được thay đổi, cập nhật hoặc cải thiện theo từng thời điểm."],
  },
  {
    id: "data",
    icon: "database",
    title: "Thông tin chúng tôi xử lý và cách sử dụng",
    paragraphs: ["Để cung cấp dịch vụ, hệ thống có thể xử lý:"],
    bullets: [
      "Nội dung hợp đồng và tài liệu bạn tải lên.",
      "Câu hỏi và yêu cầu bạn nhập vào hệ thống.",
      "Thông tin tài khoản, nếu dịch vụ yêu cầu đăng nhập.",
      "Thông tin kỹ thuật cần thiết để vận hành và bảo mật dịch vụ.",
    ],
    subtitle: "Thông tin được dùng để",
    numbered: [
      "Cung cấp chức năng bạn yêu cầu và phân tích tài liệu.",
      "Duy trì hoạt động, bảo mật hệ thống; phát hiện và xử lý lạm dụng hoặc sự cố kỹ thuật.",
      "Cải thiện chất lượng, độ ổn định của dịch vụ trong phạm vi được phép.",
      "Thực hiện nghĩa vụ pháp lý khi cần thiết.",
    ],
    after: [
      "Chúng tôi không chủ động dùng nội dung hợp đồng hoặc thông tin cá nhân của bạn cho mục đích độc lập với dịch vụ, gồm quảng cáo và tiếp thị trực tiếp, trừ khi bạn đồng ý phù hợp hoặc pháp luật cho phép hay yêu cầu.",
      "Bạn chỉ nên cung cấp thông tin cần thiết. Nếu tài liệu chứa thông tin của người khác, bạn cần bảo đảm mình có quyền cung cấp và xử lý thông tin đó.",
    ],
  },
  {
    id: "privacy",
    icon: "shield_lock",
    title: "Bảo vệ thông tin trước khi phân tích bằng AI",
    paragraphs: [
      "Trước khi gửi dữ liệu đến mô hình ngôn ngữ lớn (LLM), trong phạm vi khả năng kỹ thuật, hệ thống ưu tiên:",
    ],
    bullets: [
      "Nhận diện thông tin cá nhân (họ tên, số điện thoại, địa chỉ, số giấy tờ...).",
      "Ẩn hoặc thay thế thông tin nhận dạng không cần thiết.",
      "Giảm thiểu dữ liệu không liên quan đến yêu cầu phân tích.",
      "Giữ lại thông tin cần thiết để bảo toàn ngữ cảnh và độ chính xác.",
    ],
    after: [
      "Việc xử lý này nhằm giảm lượng thông tin cá nhân đưa vào quá trình phân tích AI, không phải cam kết mọi thông tin cá nhân trong mọi tài liệu đều được nhận diện và loại bỏ hoàn toàn.",
    ],
  },
  {
    id: "ai",
    icon: "psychology",
    title: "Độ chính xác của AI và giới hạn tư vấn",
    paragraphs: [
      "Dịch vụ dùng mô hình AI để phân tích và tạo nội dung. AI có thể hiểu chưa đầy đủ một điều khoản, bỏ sót vấn đề, nhận định chưa chính xác, diễn giải khác ý định của văn bản, hoặc không phản ánh thay đổi pháp luật và hoàn cảnh phát sinh sau thời điểm phân tích.",
      "Vì vậy chúng tôi không cam kết kết quả luôn chính xác, đầy đủ hoặc phù hợp tuyệt đối với từng trường hợp.",
      `${TERMS_PRODUCT} là công cụ hỗ trợ công nghệ, không phải dịch vụ tư vấn pháp lý. Mọi phân tích, đánh giá và khuyến nghị chỉ mang tính tham khảo. Với vấn đề phức tạp hoặc có giá trị pháp lý, tài chính đáng kể, bạn nên tham khảo luật sư hoặc chuyên gia có thẩm quyền trước khi quyết định.`,
    ],
  },
  {
    id: "duty",
    icon: "person_check",
    title: "Trách nhiệm của bạn",
    paragraphs: ["Khi sử dụng dịch vụ, bạn có trách nhiệm:"],
    bullets: [
      "Cung cấp thông tin phù hợp, chính xác trong phạm vi cần thiết.",
      "Bảo đảm có quyền sử dụng tài liệu được tải lên.",
      "Không cung cấp thông tin trái pháp luật hoặc xâm phạm quyền của người khác.",
      "Tự đánh giá kết quả; không coi kết quả AI là căn cứ duy nhất cho quyết định quan trọng.",
      "Không dùng dịch vụ cho mục đích trái pháp luật hoặc gây tổn hại cho người khác.",
    ],
  },
  {
    id: "liability",
    icon: "balance",
    title: "Giới hạn trách nhiệm",
    paragraphs: [
      "Chúng tôi nỗ lực cung cấp dịch vụ ổn định, an toàn, hữu ích, nhưng một số yếu tố nằm ngoài khả năng kiểm soát có thể ảnh hưởng đến dịch vụ. Trong phạm vi pháp luật cho phép, chúng tôi không chịu trách nhiệm đối với hậu quả phát sinh từ:",
    ],
    bullets: [
      "Thông tin do người dùng cung cấp sai, thiếu hoặc gây hiểu nhầm.",
      "Việc dùng kết quả AI mà không kiểm tra, xác minh cần thiết, hoặc dùng ngoài phạm vi chức năng của dịch vụ.",
      "Thay đổi của pháp luật hoặc hoàn cảnh thực tế sau thời điểm phân tích.",
      "Sự cố hạ tầng mạng, thiết bị, nhà cung cấp hoặc hệ thống bên ngoài nằm ngoài khả năng kiểm soát hợp lý.",
      "Dịch vụ tạm thời không khả dụng do bảo trì, nâng cấp, xử lý sự cố; hoặc sự kiện bất khả kháng.",
    ],
    after: [
      "Việc sử dụng dịch vụ không bảo đảm một giao dịch, hợp đồng hay quyết định cụ thể sẽ đạt kết quả pháp lý nhất định.",
    ],
  },
  {
    id: "storage",
    icon: "lock",
    title: "Bên thứ ba, lưu trữ và bảo mật",
    paragraphs: [
      "Một số thành phần của dịch vụ được vận hành với sự hỗ trợ của nhà cung cấp công nghệ, hạ tầng, lưu trữ hoặc AI bên thứ ba; thông tin cần thiết có thể được xử lý qua các nhà cung cấp này và đồng thời chịu sự điều chỉnh của chính sách của họ. Chúng tôi chọn các nhà cung cấp phù hợp với yêu cầu vận hành và bảo mật trong phạm vi có thể kiểm soát.",
      "Thông tin được lưu trữ trong thời gian cần thiết để cung cấp dịch vụ, duy trì hệ thống, bảo đảm an toàn, xử lý yêu cầu hỗ trợ hoặc thực hiện nghĩa vụ pháp lý. Khi không còn cần thiết, thông tin có thể được xóa, ẩn danh hoặc xử lý theo chính sách lưu trữ và quy định hiện hành. Thời gian lưu trữ khác nhau tùy loại thông tin và mục đích.",
      "Chúng tôi áp dụng biện pháp kỹ thuật và tổ chức phù hợp để bảo vệ thông tin khỏi truy cập, sử dụng hoặc tiết lộ trái phép. Tuy nhiên không phương thức truyền tải hay lưu trữ nào trên Internet bảo đảm an toàn tuyệt đối. Khi có sự cố ảnh hưởng đến thông tin người dùng, chúng tôi sẽ xử lý phù hợp theo khả năng kiểm soát và yêu cầu của pháp luật.",
    ],
  },
  {
    id: "rights",
    icon: "key",
    title: "Quyền của bạn",
    paragraphs: ["Tùy quy định pháp luật áp dụng, bạn có thể có quyền:"],
    bullets: [
      "Yêu cầu truy cập thông tin của mình.",
      "Yêu cầu chỉnh sửa thông tin không chính xác.",
      "Yêu cầu xóa thông tin trong trường hợp phù hợp.",
      "Yêu cầu hạn chế hoặc phản đối một số hoạt động xử lý, và các quyền khác theo pháp luật.",
    ],
    after: [
      "Yêu cầu sẽ được xem xét dựa trên loại dữ liệu, mục đích xử lý, khả năng kỹ thuật và quy định hiện hành.",
    ],
  },
  {
    id: "consent",
    icon: "task_alt",
    title: "Thay đổi chính sách và chấp thuận",
    paragraphs: [
      "Chúng tôi có thể cập nhật Chính sách để phản ánh thay đổi về chức năng, công nghệ, cách xử lý thông tin, quy trình bảo mật hoặc pháp luật. Phiên bản mới nhất được công bố trên hệ thống; với thay đổi quan trọng, chúng tôi có thể thông báo qua các phương thức phù hợp.",
      'Bằng việc nhấn "Đồng ý và tiếp tục", tải tài liệu lên hoặc sử dụng các chức năng của hệ thống, bạn xác nhận rằng:',
    ],
    bullets: [
      "Bạn đã đọc và hiểu Chính sách này.",
      "Bạn hiểu kết quả AI chỉ mang tính hỗ trợ, tham khảo và có thể chưa chính xác hoặc chưa đầy đủ.",
      "Bạn đồng ý để thông tin được xử lý theo các nguyên tắc trong Chính sách.",
      "Bạn chịu trách nhiệm về quyết định cuối cùng dựa trên kết quả của hệ thống.",
    ],
    after: ["Nếu không đồng ý, vui lòng không tiếp tục sử dụng dịch vụ."],
  },
];
