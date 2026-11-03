export const TERMS_PRODUCT = "ContractLens";
export const TERMS_VERSION = "1.0";
export const TERMS_EFFECTIVE_DATE = "19/08/2026";
export const TERMS_TITLE = "Chính sách sử dụng dịch vụ và bảo vệ thông tin";

export const TERMS_INTRO = [
  `Chào mừng bạn đến với ${TERMS_PRODUCT}.`,
  "Trước khi sử dụng dịch vụ, vui lòng đọc kỹ Chính sách này để hiểu cách chúng tôi xử lý thông tin của bạn, cách hệ thống AI thực hiện phân tích và những giới hạn cần lưu ý khi sử dụng kết quả.",
  "Việc tiếp tục sử dụng dịch vụ đồng nghĩa với việc bạn xác nhận đã đọc và đồng ý với các nội dung dưới đây.",
];

export const TERMS_SECTIONS = [
  {
    id: "1",
    title: "1. Điều bạn cần biết trước khi sử dụng",
    callouts: [
      {
        heading: "Thông tin của bạn được sử dụng đúng mục đích",
        body: [
          "Thông tin và tài liệu bạn cung cấp được sử dụng để cung cấp các chức năng mà bạn yêu cầu, chẳng hạn như phân tích hợp đồng, nhận diện rủi ro và đưa ra khuyến nghị.",
          "Chúng tôi không chủ động sử dụng nội dung hợp đồng hoặc thông tin người dùng cho quảng cáo, tiếp thị, xây dựng hồ sơ cá nhân hoặc các mục đích độc lập khác với việc cung cấp và vận hành dịch vụ, trừ khi có sự đồng ý phù hợp của bạn hoặc pháp luật có quy định khác.",
        ],
      },
      {
        heading: "Hạn chế thông tin cá nhân khi sử dụng AI",
        body: [
          "Trước khi nội dung được gửi đến mô hình AI để phân tích, hệ thống ưu tiên nhận diện và ẩn, loại bỏ hoặc thay thế các thông tin cá nhân và thông tin nhạy cảm không cần thiết cho quá trình phân tích, trong phạm vi khả năng kỹ thuật.",
          "Mục tiêu là hạn chế việc thông tin nhận dạng cá nhân được đưa vào quá trình xử lý của mô hình AI khi những thông tin đó không cần thiết để phân tích hợp đồng.",
        ],
      },
      {
        heading: "AI chỉ hỗ trợ phân tích",
        body: [
          "Kết quả do AI cung cấp nhằm hỗ trợ bạn nhận diện vấn đề, đánh giá rủi ro và xem xét các điều khoản trong hợp đồng.",
          "Kết quả không phải là tư vấn pháp lý chính thức và không thay thế ý kiến của luật sư hoặc chuyên gia pháp lý.",
        ],
      },
      {
        heading: "Bạn nên kiểm tra trước khi quyết định",
        body: [
          "AI có thể mắc lỗi hoặc không hiểu đầy đủ một tình huống cụ thể. Hãy kiểm tra lại kết quả với hợp đồng, hoàn cảnh thực tế và quy định pháp luật hiện hành trước khi ký kết hoặc thực hiện giao dịch.",
        ],
      },
    ],
  },
  {
    id: "2",
    title: "2. Phạm vi dịch vụ",
    paragraphs: [
      `${TERMS_PRODUCT} cung cấp các công cụ hỗ trợ người dùng phân tích và xem xét hợp đồng bằng công nghệ trí tuệ nhân tạo.`,
      "Tùy thuộc vào từng phiên bản dịch vụ, các chức năng có thể bao gồm:",
    ],
    bullets: [
      "Phân tích nội dung hợp đồng.",
      "Nhận diện các điều khoản có khả năng phát sinh rủi ro.",
      "Giải thích nội dung và điều khoản.",
      "Đề xuất các điểm cần xem xét hoặc điều chỉnh.",
      "Trả lời câu hỏi liên quan đến nội dung hợp đồng.",
      "Các chức năng hỗ trợ khác được cung cấp trên hệ thống.",
    ],
    after: [
      "Phạm vi và tính năng của dịch vụ có thể được thay đổi, cập nhật hoặc cải thiện theo từng thời điểm.",
    ],
  },
  {
    id: "3",
    title: "3. Thông tin chúng tôi xử lý",
    paragraphs: [
      "Để cung cấp dịch vụ, hệ thống có thể xử lý:",
    ],
    bullets: [
      "Nội dung hợp đồng và tài liệu bạn tải lên.",
      "Câu hỏi và yêu cầu bạn nhập vào hệ thống.",
      "Thông tin cần thiết để thực hiện phân tích.",
      "Thông tin tài khoản, nếu dịch vụ yêu cầu đăng nhập.",
      "Một số thông tin kỹ thuật cần thiết để vận hành, bảo mật và duy trì dịch vụ.",
    ],
    after: [
      "Bạn nên chỉ cung cấp những thông tin cần thiết cho mục đích sử dụng dịch vụ.",
      "Nếu tài liệu chứa thông tin của người khác, bạn cần bảo đảm rằng mình có quyền cung cấp và xử lý những thông tin đó.",
    ],
  },
  {
    id: "4",
    title: "4. Cách chúng tôi sử dụng thông tin",
    paragraphs: ["Thông tin được sử dụng để:"],
    numbered: [
      "Cung cấp chức năng mà bạn yêu cầu.",
      "Phân tích và xử lý tài liệu được cung cấp.",
      "Duy trì hoạt động và bảo mật hệ thống.",
      "Phát hiện, ngăn chặn và xử lý các hành vi lạm dụng hoặc sự cố kỹ thuật.",
      "Cải thiện chất lượng và độ ổn định của dịch vụ trong phạm vi được phép.",
      "Thực hiện các nghĩa vụ pháp lý khi cần thiết.",
    ],
    subtitle: "Không sử dụng ngoài mục đích",
    after: [
      "Chúng tôi cam kết không chủ động sử dụng nội dung hợp đồng hoặc thông tin cá nhân mà bạn cung cấp cho các mục đích độc lập với dịch vụ, bao gồm quảng cáo hoặc tiếp thị trực tiếp, trừ khi bạn có sự đồng ý phù hợp hoặc việc xử lý được pháp luật cho phép hoặc yêu cầu.",
    ],
  },
  {
    id: "5",
    title: "5. Bảo vệ thông tin trước khi phân tích bằng AI",
    paragraphs: [
      "Đối với nội dung được đưa vào chức năng phân tích hợp đồng, hệ thống có thể thực hiện bước xử lý trước khi gửi dữ liệu đến mô hình ngôn ngữ lớn (LLM).",
      "Trong phạm vi khả năng kỹ thuật, hệ thống sẽ ưu tiên:",
    ],
    bullets: [
      "Nhận diện thông tin cá nhân.",
      "Ẩn hoặc thay thế thông tin nhận dạng không cần thiết.",
      "Giảm thiểu dữ liệu không liên quan đến yêu cầu phân tích.",
      "Giữ lại thông tin cần thiết để duy trì ngữ cảnh và độ chính xác của phân tích.",
    ],
    after: [
      "Ví dụ, các thông tin như họ tên, số điện thoại, địa chỉ, số giấy tờ hoặc thông tin nhận dạng tương tự có thể được ẩn hoặc thay thế khi không cần thiết cho việc phân tích.",
      "Việc xử lý này nhằm giảm thiểu lượng thông tin cá nhân được đưa vào quá trình phân tích AI, không phải là cam kết rằng mọi thông tin cá nhân trong mọi tài liệu đều có thể được nhận diện và loại bỏ hoàn toàn.",
    ],
  },
  {
    id: "6",
    title: "6. Công nghệ AI và độ chính xác của kết quả",
    paragraphs: [
      "Dịch vụ sử dụng các mô hình trí tuệ nhân tạo để phân tích và tạo nội dung.",
      "AI có thể:",
    ],
    bullets: [
      "Hiểu chưa đầy đủ một điều khoản.",
      "Bỏ sót một vấn đề.",
      "Đưa ra nhận định chưa chính xác.",
      "Diễn giải khác với ý định của văn bản.",
      "Không phản ánh những thay đổi pháp luật hoặc hoàn cảnh phát sinh sau thời điểm phân tích.",
    ],
    after: [
      "Do đó, chúng tôi không cam kết rằng kết quả AI luôn chính xác, đầy đủ hoặc phù hợp tuyệt đối với từng trường hợp cụ thể.",
      "Kết quả được cung cấp dựa trên thông tin và dữ liệu mà hệ thống có thể xử lý tại thời điểm yêu cầu.",
    ],
  },
  {
    id: "7",
    title: "7. Không phải tư vấn pháp lý",
    paragraphs: [
      `${TERMS_PRODUCT} là công cụ hỗ trợ công nghệ và không phải là dịch vụ tư vấn pháp lý.`,
      "Các phân tích, đánh giá rủi ro, giải thích và khuyến nghị được tạo bởi AI chỉ nhằm mục đích tham khảo.",
      "Đối với các vấn đề có tính chất phức tạp hoặc có giá trị pháp lý, tài chính đáng kể, bạn nên tham khảo ý kiến luật sư hoặc chuyên gia có thẩm quyền trước khi đưa ra quyết định.",
    ],
  },
  {
    id: "8",
    title: "8. Trách nhiệm của người sử dụng",
    paragraphs: ["Khi sử dụng dịch vụ, bạn có trách nhiệm:"],
    bullets: [
      "Cung cấp thông tin phù hợp và chính xác trong phạm vi cần thiết.",
      "Đảm bảo bạn có quyền sử dụng tài liệu được tải lên.",
      "Không cung cấp thông tin trái pháp luật hoặc xâm phạm quyền của người khác.",
      "Tự đánh giá kết quả trước khi sử dụng.",
      "Không sử dụng kết quả AI như căn cứ duy nhất cho các quyết định quan trọng.",
      "Không sử dụng dịch vụ cho mục đích trái pháp luật hoặc gây tổn hại cho người khác.",
    ],
  },
  {
    id: "9",
    title: "9. Giới hạn trách nhiệm",
    paragraphs: [
      "Chúng tôi nỗ lực cung cấp dịch vụ ổn định, an toàn và hữu ích, nhưng do đặc điểm của công nghệ AI và môi trường Internet, một số yếu tố nằm ngoài khả năng kiểm soát của chúng tôi có thể ảnh hưởng đến dịch vụ.",
      "Trong phạm vi pháp luật cho phép, chúng tôi không chịu trách nhiệm đối với hậu quả phát sinh từ:",
    ],
    bullets: [
      "Việc người dùng cung cấp thông tin sai, thiếu hoặc gây hiểu nhầm.",
      "Việc người dùng sử dụng kết quả AI mà không kiểm tra hoặc xác minh cần thiết.",
      "Việc sử dụng kết quả ngoài phạm vi chức năng của dịch vụ.",
      "Những thay đổi của pháp luật hoặc hoàn cảnh thực tế sau thời điểm phân tích.",
      "Sự cố do hạ tầng mạng, thiết bị, nhà cung cấp dịch vụ hoặc các hệ thống bên ngoài nằm ngoài khả năng kiểm soát hợp lý.",
      "Việc dịch vụ tạm thời không khả dụng do bảo trì, nâng cấp hoặc xử lý sự cố.",
      "Các sự kiện bất khả kháng theo quy định pháp luật.",
    ],
    after: [
      "Việc sử dụng dịch vụ không tạo ra cam kết rằng một giao dịch, hợp đồng hoặc quyết định cụ thể sẽ đạt được một kết quả pháp lý nhất định.",
    ],
  },
  {
    id: "10",
    title: "10. Dịch vụ của bên thứ ba",
    paragraphs: [
      "Một số thành phần của dịch vụ có thể được vận hành với sự hỗ trợ của các nhà cung cấp công nghệ, hạ tầng, lưu trữ hoặc dịch vụ AI bên thứ ba.",
      "Thông tin cần thiết có thể được xử lý thông qua các nhà cung cấp này để thực hiện chức năng tương ứng.",
      "Chúng tôi lựa chọn và sử dụng các dịch vụ bên thứ ba phù hợp với yêu cầu vận hành và bảo mật của hệ thống trong phạm vi có thể kiểm soát.",
      "Việc xử lý dữ liệu bởi các nhà cung cấp bên thứ ba có thể đồng thời chịu sự điều chỉnh của chính sách và điều khoản dịch vụ tương ứng.",
    ],
  },
  {
    id: "11",
    title: "11. Lưu trữ và xóa thông tin",
    paragraphs: [
      "Thông tin có thể được lưu trữ trong khoảng thời gian cần thiết để cung cấp dịch vụ, duy trì hệ thống, bảo đảm an toàn, xử lý yêu cầu hỗ trợ hoặc thực hiện nghĩa vụ pháp lý.",
      "Khi không còn nhu cầu lưu trữ, thông tin có thể được xóa, ẩn danh hoặc xử lý theo chính sách lưu trữ của hệ thống và quy định pháp luật hiện hành.",
      "Thời gian lưu trữ có thể khác nhau tùy thuộc vào loại thông tin và mục đích xử lý.",
    ],
  },
  {
    id: "12",
    title: "12. Bảo mật",
    paragraphs: [
      "Chúng tôi áp dụng các biện pháp kỹ thuật và tổ chức phù hợp nhằm bảo vệ thông tin khỏi việc truy cập, sử dụng hoặc tiết lộ trái phép.",
      "Tuy nhiên, không có phương thức truyền tải hoặc lưu trữ thông tin nào trên Internet có thể bảo đảm an toàn tuyệt đối.",
      "Trong trường hợp phát hiện sự cố ảnh hưởng đến thông tin người dùng, chúng tôi sẽ thực hiện các biện pháp xử lý phù hợp theo khả năng kiểm soát và yêu cầu của pháp luật áp dụng.",
    ],
  },
  {
    id: "13",
    title: "13. Quyền của người dùng",
    paragraphs: [
      "Tùy thuộc vào quy định pháp luật áp dụng, bạn có thể có quyền:",
    ],
    bullets: [
      "Yêu cầu truy cập thông tin của mình.",
      "Yêu cầu chỉnh sửa thông tin không chính xác.",
      "Yêu cầu xóa thông tin trong trường hợp phù hợp.",
      "Yêu cầu hạn chế hoặc phản đối một số hoạt động xử lý.",
      "Thực hiện các quyền khác theo quy định pháp luật.",
    ],
    after: [
      "Các yêu cầu sẽ được xem xét dựa trên loại dữ liệu, mục đích xử lý, khả năng kỹ thuật và quy định pháp luật hiện hành.",
    ],
  },
  {
    id: "14",
    title: "14. Thay đổi chính sách",
    paragraphs: [
      "Chúng tôi có thể cập nhật Chính sách này để phản ánh thay đổi về:",
    ],
    bullets: [
      "Chức năng và công nghệ của dịch vụ.",
      "Phương thức xử lý thông tin.",
      "Quy trình bảo mật.",
      "Quy định pháp luật áp dụng.",
    ],
    after: [
      "Phiên bản mới nhất sẽ được công bố trên hệ thống. Đối với những thay đổi quan trọng, chúng tôi có thể thông báo cho người dùng thông qua các phương thức phù hợp.",
    ],
  },
  {
    id: "15",
    title: "15. Chấp thuận sử dụng dịch vụ",
    paragraphs: [
      'Bằng việc nhấn "Đồng ý và tiếp tục", tải tài liệu lên hoặc sử dụng các chức năng của hệ thống, bạn xác nhận rằng:',
    ],
    bullets: [
      "Bạn đã đọc và hiểu Chính sách này.",
      "Bạn hiểu rằng kết quả AI chỉ mang tính hỗ trợ và tham khảo.",
      "Bạn hiểu rằng AI có thể tạo ra kết quả chưa chính xác hoặc chưa đầy đủ.",
      "Bạn đồng ý với việc thông tin được xử lý theo các nguyên tắc được mô tả trong Chính sách.",
      "Bạn chịu trách nhiệm đối với quyết định cuối cùng được đưa ra dựa trên thông tin và kết quả của hệ thống.",
    ],
    after: [
      "Nếu bạn không đồng ý với Chính sách này, vui lòng không tiếp tục sử dụng dịch vụ.",
    ],
  },
];

export const TERMS_SUMMARY = {
  title: "Tóm tắt nhanh",
  quote:
    "Bạn cung cấp thông tin → Hệ thống xử lý để thực hiện chức năng bạn yêu cầu → Thông tin cá nhân không cần thiết được ưu tiên ẩn/giảm thiểu trước khi phân tích AI → AI tạo kết quả hỗ trợ → Bạn kiểm tra và quyết định.",
  note: "Kết quả AI không phải là tư vấn pháp lý và không thay thế ý kiến của luật sư hoặc chuyên gia pháp lý.",
};
