module ApplicationHelper
  def navbar_active_link_script
    javascript_tag do
      %Q(
        $(document).ready(function() {
          var currentPageLink = $('a[href="' + this.location.pathname + '"]');
          currentPageLink.closest("ul.nav li").addClass('active');
        });
      ).html_safe
    end
  end
end
