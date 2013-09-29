class EmergencyContact < ActiveRecord::Base
  belongs_to :user

  def to_s
    name
  end
end
