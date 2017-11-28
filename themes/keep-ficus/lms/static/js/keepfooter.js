(function() {
  var root, source;

  source = "<div class=\"keepfooter\">\n  <div class=\"container\">\n    <div class=\"row\">\n      <div class=\"col-md-6\">\n        <i class=\"keeplogo-logo_KEEP_horizontal\"></i>\n        <div>{{a1}}</div>\n        <div>{{a2}}</div>\n        <div>{{a3}}</div>\n      </div>\n      <div class=\"col-md-2\">\n        <a href=\"https://keep.edu.hk/{{locale}}/media-kit\">{{p0}}</a>\n        <a href=\"https://keep.edu.hk/{{locale}}/faq\">{{p1}}</a>\n        <a href=\"https://keep.edu.hk/{{locale}}/terms\">{{p2}}</a>\n        <a href=\"https://keep.edu.hk/{{locale}}/feedback\" onclick=\"openFeedbackWindow($(this)); return false\">{{p3}}</a>\n      </div>\n      <div class=\"col-md-2\">\n        <a href=\"https://search.keep.edu.hk\">{{k1}}</a>\n        <a href=\"https://catalog.keep.edu.hk\">{{k2}}</a>\n        <a href=\"https://course.keep.edu.hk\">{{k3}}</a>\n        <a href=\"https://poll.keep.edu.hk\">{{k4}}</a>\n      </div>\n      <div class=\"col-md-2\">\n        <a href=\"https://keep.edu.hk/{{locale}}/about\">{{p4}}</a>\n        <a href=\"https://keep.edu.hk/{{locale}}/news\">{{p5}}</a>\n        <a href=\"https://keep.edu.hk/{{locale}}/team\">{{p6}}</a>\n        <a href=\"https://keep.edu.hk/{{locale}}/contact\">{{p7}}</a>\n      </div>\n    </div>\n    <div class=\"row\"><div class=\"copyright col-md-9\"><span>Copyright &copy; 2014-{{year}} KEEP. The Chinese University of Hong Kong. All rights reserved.</span><br/><span class=\"copyright2\">&copy; KEEP Open edX. All rights reserved except where noted. EdX, Open edX and the edX and Open EdX logos are registered trademarks or trademarks of edX Inc.</span></div><div class=\"col-md-3 edxLogo\"><a href=\"http://open.edx.org\"><img src=\"https://files.edx.org/openedx-logos/edx-openedx-logo-tag.png\" alt=\"Powered by Open edX\" width=\"62.5\"></a></div></div>\n  </div>\n</div>";

  root = typeof exports !== "undefined" && exports !== null ? exports : this;

  root.keepfooter = function(textColor, lang) {
    var address1, address2, address3, context, html, keep1, keep2, keep3, keep4, page0, page1, page2, page3, page4, page5, page6, page7, template;
    if (lang == null) {
      lang = 'en';
    }
    address1 = {
      en: "6/F, Hui Yeung Shing Building",
      cn: "香港特别行政区新界沙田",
      hk: "香港特別行政區新界沙田"
    };
    address2 = {
      en: "The Chinese University of Hong Kong",
      cn: "香港中文大学",
      hk: "香港中文大學"
    };
    address3 = {
      en: "Sha Tin, N.T. Hong Kong",
      cn: "许让成楼6楼",
      hk: "許讓成樓6樓"
    };
    page0 = {
      en: "Media Kit",
      cn: "媒体数据包",
      hk: "傳媒資料包"
    };
    page1 = {
      en: "FAQ",
      cn: "常见问题",
      hk: "常見問題"
    };
    page2 = {
      en: "Terms & Conditions",
      cn: "条款",
      hk: "條款及細則"
    };
    page3 = {
      en: "Feedback",
      cn: "回馈",
      hk: "提交意見"
    };
    page4 = {
      en: "About KEEP",
      cn: "关于KEEP",
      hk: "關於KEEP"
    };
    page5 = {
      en: "News & Events",
      cn: "新闻消息",
      hk: "新聞活動"
    };
    page6 = {
      en: "Team",
      cn: "团队介绍",
      hk: "團隊介紹"
    };
    page7 = {
      en: "Contact Us",
      cn: "联系我们",
      hk: "聯絡我們"
    };
    keep1 = {
      en: "KEEPSearch",
      cn: "KEEPSearch",
      hk: "KEEPSearch"
    };
    keep2 = {
      en: "KEEPCatalog",
      cn: "KEEPCatalog",
      hk: "KEEPCatalog"
    };
    keep3 = {
      en: "KEEPCourse",
      cn: "KEEPCourse",
      hk: "KEEPCourse"
    };
    keep4 = {
      en: "KEEPoll",
      cn: "KEEPoll",
      hk: "KEEPoll"
    };
    context = {
      year: new Date().getFullYear(),
      a1: address1[lang],
      a2: address2[lang],
      a3: address3[lang],
      p0: page0[lang],
      p1: page1[lang],
      p2: page2[lang],
      p3: page3[lang],
      p4: page4[lang],
      p5: page5[lang],
      p6: page6[lang],
      p7: page7[lang],
      k1: keep1[lang],
      k2: keep2[lang],
      k3: keep3[lang],
      k4: keep4[lang],
      locale: lang
    };
    template = Handlebars.compile(source);
    html = template(context);
    return $('#keepfooter').after(html);
  };

  root.openFeedbackWindow = function(link) {
    var height, left, options, top, url, width;
    url = link.attr("href");
    width = 1100;
    height = 638;
    left = ($(window).width() - width) / 2;
    top = ($(window).height() - height) / 2;
    options = "width=" + width + ",height=" + height + ",top=" + top + ",left=" + left + ",resizable=yes,scrollbars=yes";
    return window.open(url, "", options);
  };

}).call(this);
