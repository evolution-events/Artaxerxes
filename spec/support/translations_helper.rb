require 'yaml'

module RSpec
  module TranslationsHelper
    def translation_keys_in(filename)
      hash = YAML.load_file(filename)
      language_name = hash.keys.first

      collector = KeyCollector.new(hash[language_name])
      collector.all_translation_keys
    end

    class KeyCollector
      attr_accessor :hash

      def initialize(hash)
        @hash = hash
      end

      def all_translation_keys
        hash.keys.inject [] do |keys, key|
          current_value = hash[key]

          if current_value.is_a? Hash
            subkeys = self.class.new(current_value).all_translation_keys

            keys += subkeys.map do |subkey|
              "#{key}.#{subkey}"
            end
          else
            keys << "#{key}"
          end
        end
      end
    end
  end
end

