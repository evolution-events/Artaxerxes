class UserAddress < ActiveRecord::Base
  belongs_to :user

  def to_s
    "#{address}, #{postal_code}, #{city}, #{country}"
  end
end
