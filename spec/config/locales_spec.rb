require File.join(Dir.pwd, "spec/support/translations_helper.rb")

describe "the language files" do
  include RSpec::TranslationsHelper

  pattern = "config/locales/*.yml"

  locale_files = Dir.glob(pattern).reject do |filename|
    # do not test files that only contain framework-related translations
    filename =~ /rails/
  end

  base_language_file = locale_files.pop
  base_language = File.basename(base_language_file, ".yml")

  locale_files.each do |other_language_file|
    other_language = File.basename(other_language_file, ".yml")

    describe " for :#{base_language} and :#{other_language}" do
      specify "contain the same translations" do
        keys_first = translation_keys_in(base_language_file)
        keys_other = translation_keys_in(other_language_file)

        # Using this syntax provides more meaningful output on failure,
        # where the difference is reflected, instead of both arrays
        (keys_first - keys_other).should == []
        (keys_other - keys_first).should == []
      end
    end
  end
end
