class AddIndices < ActiveRecord::Migration
  def change
    add_index :medical_details, :user_id
    add_index :events, :series_id
    add_index :user_addresses, :user_id
  end
end
