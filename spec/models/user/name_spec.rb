#encoding: utf-8

require 'spec_helper'

describe User do
  describe :name do
    context "when the user has prepositions in his/her name" do
      let(:user) { User.new(first_name: 'André', preposition: 'van', last_name: 'Duin',) }

      it "returns a name with the first_name and last_name included" do
        user.name.should == "André van Duin"
      end
    end

    context "when the user has no prepositions in his/her name" do
      let(:user) { User.new(first_name: 'Piet', last_name: 'Snot') }

      it "returns a name with the first_name and last_name included" do
        user.name.should == "Piet Snot"
      end
    end
  end
end
