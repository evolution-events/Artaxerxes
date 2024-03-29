$(function() {
    // Hide options with dependencies when the dependencies are not met.
    // Also remove the required attribute from them, otherwise the
    // browser will refuse to submit the form (but also hide the error
    // message...).
    $(".registration-options-form [data-depends-name]").each(function() {
        var elem = $(this)
        var name = elem.attr('data-depends-name')
        var value = elem.attr('data-depends-value')
        var select = $(this).closest('form').find('select[name="' + name + '"]')
        // If the select is not present, this means it can no longer be
        // changed and has the right value selected (if it had a
        // different value, the depending field would have been omitted).
        if (!select.length)
            return;

        elem.find('[required]').attr('data-required', true);
        function update() {
            if (select.val() == value) {
                elem.find('[data-required]').attr('required', true)
                elem.show()
            } else {
                elem.hide()
                elem.find('[required]').removeAttr('required')
            }
        }
        update()
        select.change(update)
    })
})
