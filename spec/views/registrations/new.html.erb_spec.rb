require 'spec_helper'

describe "registrations/new" do
  before(:each) do
    assign(:registration, stub_model(Registration,
      :user => nil,
      :event => nil,
      :status => "MyString"
    ).as_new_record)
  end

  it "renders new registration form" do
    render

    # Run the generator again with the --webrat flag if you want to use webrat matchers
    assert_select "form[action=?][method=?]", registrations_path, "post" do
      assert_select "select#registration_user[name=?]", "registration[user]"
      assert_select "select#registration_event[name=?]", "registration[event]"
      assert_select "input#registration_status[name=?]", "registration[status]"
    end
  end
end
