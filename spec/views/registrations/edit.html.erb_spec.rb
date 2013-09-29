require 'spec_helper'

describe "registrations/edit" do
  before(:each) do
    @registration = assign(:registration, stub_model(Registration,
      :user => nil,
      :event => nil,
      :status => "MyString"
    ))
  end

  it "renders the edit registration form" do
    render

    # Run the generator again with the --webrat flag if you want to use webrat matchers
    assert_select "form[action=?][method=?]", registration_path(@registration), "post" do
      assert_select "input#registration_user[name=?]", "registration[user]"
      assert_select "input#registration_event[name=?]", "registration[event]"
      assert_select "input#registration_status[name=?]", "registration[status]"
    end
  end
end
